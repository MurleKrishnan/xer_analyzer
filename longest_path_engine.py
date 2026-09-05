"""
LONGEST PATH ENGINE
====================
Computes the true "Longest Path" (Driving Critical Path) using backward-pass
graph traversal — the industry-standard method for forensic delay analysis.

Unlike TF ≤ 0 heuristic (which can be distorted by constraints), Longest Path
traces the actual chain of driving predecessors from project completion 
back to project start.

Algorithm:
1. Identify project finish milestone(s) — activity with latest early_finish + no successors
2. From each finish node, walk backward through predecessors
3. For each activity, select the predecessor with the LATEST early_finish
   (that is the "driving" predecessor)
4. Continue until reaching a start milestone or no more predecessors
5. Mark all activities in the traced chain as "on longest path"
"""

from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class LongestPathEngine:
    """Native CPM Longest Path Calculator."""

    def __init__(self, engine):
        self.engine = engine
        self.longest_path_ids = set()
        self.longest_path_chain = []
        self.driving_edges = []  # List of (pred_id, succ_id, lag_days) tuples
        self.results = {}

    def calculate(self):
        """Run longest path calculation."""
        logger.info("🎯 Calculating Longest Path (driving critical path)...")
        
        try:
            # Step 1: Find project finish milestone(s)
            finish_nodes = self._find_finish_nodes()
            if not finish_nodes:
                logger.warning("No project finish node found for Longest Path calculation.")
                self.results = {'error': 'No project finish node identified.'}
                return self.results
            
            logger.info(f"  Found {len(finish_nodes)} candidate finish node(s)")
            
            # Step 2: Trace backward from each finish node
            for finish_node in finish_nodes:
                self._trace_backward(finish_node)
            
            # Step 3: Build ordered chain from finish backward to start
            self.longest_path_chain = self._build_ordered_chain(finish_nodes)
            
            # Step 4: Compile results
            self.results = self._compile_results()
            
            logger.info(f"  ✅ Longest Path identified: {len(self.longest_path_ids)} activities")
        except Exception as e:
            logger.exception("Longest Path calculation error: %s", e)
            self.results = {'error': str(e)}
        
        return self.results

    def _find_finish_nodes(self):
        """
        Identify project finish nodes:
        - Activities with no successors (or all successors are external/completed)
        - Prioritize incomplete finish milestones
        - Fall back to latest early_finish activity
        """
        candidates = []
        
        for act in self.engine.activities:
            if act.get('task_type') in ('TT_WBS', 'TT_LOE'):
                continue
            
            task_id = str(act.get('task_id', ''))
            succs = self.engine.successors.get(task_id, [])
            
            # No successors = potential finish node
            if not succs:
                ef = act.get('early_end_date_parsed') or act.get('target_end_date_parsed')
                if ef:
                    candidates.append({
                        'id': task_id,
                        'act': act,
                        'ef': ef,
                        'is_milestone': act.get('task_type') in ('TT_Mile', 'TT_FinMile'),
                        'is_complete': act.get('status_code') == 'TK_Complete',
                    })
        
        if not candidates:
            return []
        
        # Prefer incomplete finish milestones
        incomplete_milestones = [c for c in candidates if c['is_milestone'] and not c['is_complete']]
        if incomplete_milestones:
            # Return the one with latest EF
            best = max(incomplete_milestones, key=lambda c: c['ef'])
            return [best['id']]
        
        # Otherwise, take the single activity with latest EF
        best = max(candidates, key=lambda c: c['ef'])
        return [best['id']]

    def _trace_backward(self, start_node_id):
        """
        Backward pass from start_node_id.
        For each activity, find its DRIVING predecessor (the one with latest EF).
        Add that predecessor to longest_path_ids, then recurse.
        """
        visited = set()
        stack = [start_node_id]
        
        while stack:
            current_id = stack.pop()
            if current_id in visited:
                continue
            visited.add(current_id)
            self.longest_path_ids.add(current_id)
            
            # Get predecessors of current activity
            preds = self.engine.predecessors.get(current_id, [])
            if not preds:
                continue
            
            # Find the "driving" predecessor (latest EF among preds)
            driving_pred = None
            latest_ef = None
            
            for pred in preds:
                pred_id = str(pred.get('task_id', ''))
                pred_act = self.engine.activity_by_id.get(pred_id)
                if not pred_act:
                    continue
                
                pred_ef = pred_act.get('early_end_date_parsed') or pred_act.get('target_end_date_parsed')
                if not pred_ef:
                    continue
                
                if latest_ef is None or pred_ef > latest_ef:
                    latest_ef = pred_ef
                    driving_pred = pred
            
            if driving_pred:
                driving_pred_id = str(driving_pred.get('task_id', ''))
                self.driving_edges.append({
                    'pred_id': driving_pred_id,
                    'succ_id': current_id,
                    'lag_days': driving_pred.get('lag_days', 0),
                    'type': driving_pred.get('type', ''),
                })
                stack.append(driving_pred_id)

    def _build_ordered_chain(self, finish_nodes):
        """
        Return the longest path as an ordered list from start to finish.
        Uses topological ordering based on early_start dates.
        """
        chain = []
        for act_id in self.longest_path_ids:
            act = self.engine.activity_by_id.get(act_id)
            if not act:
                continue
            es = act.get('early_start_date_parsed') or act.get('target_start_date_parsed')
            chain.append({
                'id': act_id,
                'code': act.get('task_code', ''),
                'name': act.get('task_name', ''),
                'wbs': act.get('wbs_name', ''),
                'early_start': es.strftime('%Y-%m-%d') if es else '',
                'early_finish': act.get('early_end_date_parsed').strftime('%Y-%m-%d') if act.get('early_end_date_parsed') else '',
                'duration_days': round(float(act.get('original_duration_days', 0) or 0), 1),
                'total_float_days': round(float(act.get('total_float_days', 0) or 0), 1),
                'status': act.get('status_text', ''),
                'is_milestone': act.get('task_type') in ('TT_Mile', 'TT_FinMile'),
                'is_completed': act.get('status_code') == 'TK_Complete',
                '_sort_date': es or datetime.min,
            })
        
        # Sort chronologically
        chain.sort(key=lambda x: x['_sort_date'])
        for item in chain:
            del item['_sort_date']
        
        return chain

    def _compile_results(self):
        """Build final results dictionary."""
        # Compute total path duration (finish - start of first activity)
        if self.longest_path_chain:
            first_act = self.engine.activity_by_id.get(self.longest_path_chain[0]['id'])
            last_act = self.engine.activity_by_id.get(self.longest_path_chain[-1]['id'])
            path_start = first_act.get('early_start_date_parsed') if first_act else None
            path_end = last_act.get('early_end_date_parsed') if last_act else None
            total_days = (path_end - path_start).days if (path_start and path_end) else 0
        else:
            total_days = 0
        
        # Comparison to TF ≤ 0 critical
        tf_critical_ids = {
            str(a.get('task_id', '')) 
            for a in self.engine.activities 
            if a.get('is_critical') and a.get('task_type') not in ('TT_LOE', 'TT_WBS')
        }
        
        overlap = self.longest_path_ids & tf_critical_ids
        only_in_lp = self.longest_path_ids - tf_critical_ids
        only_in_tf = tf_critical_ids - self.longest_path_ids
        
        # Stats
        real_activity_count = sum(
            1 for a in self.engine.activities 
            if a.get('task_type') not in ('TT_WBS', 'TT_LOE') 
            and a.get('status_code') != 'TK_Complete'
        ) or 1
        
        lp_pct = round(len(self.longest_path_ids) / real_activity_count * 100, 2)
        tf_pct = round(len(tf_critical_ids) / real_activity_count * 100, 2)
        
        return {
            'longest_path_count': len(self.longest_path_ids),
            'longest_path_ids': list(self.longest_path_ids),
            'longest_path_chain': self.longest_path_chain,
            'driving_edges': self.driving_edges,
            'total_path_duration_days': total_days,
            'longest_path_percentage': lp_pct,
            'tf_critical_percentage': tf_pct,
            'overlap_count': len(overlap),
            'only_in_longest_path': len(only_in_lp),
            'only_in_tf_critical': len(only_in_tf),
            'agreement_pct': round(len(overlap) / max(len(self.longest_path_ids), 1) * 100, 2),
        }
