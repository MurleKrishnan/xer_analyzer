/*
    GANTT CHART LOGIC
    =================
    Fetches activity data and renders it as a Gantt chart.
*/

let gantt = null;
let currentTasks = [];

document.addEventListener('DOMContentLoaded', function() {
    loadGantt();
});

function loadGantt() {
    const maxActs = document.getElementById('maxActivities').value;
    
    document.getElementById('loadingMessage').style.display = 'block';
    document.getElementById('ganttContainer').style.display = 'none';
    
    fetch(`/api/gantt-data?max=${maxActs}`)
        .then(response => response.json())
        .then(response => {
            if (response.error) {
                document.getElementById('loadingMessage').innerHTML = 
                    `<p style="color:red;">❌ ${response.error}</p>
                     <a href="/" class="btn btn-primary">Go to Dashboard</a>`;
                return;
            }
            
            currentTasks = response.data.tasks;
            
            if (currentTasks.length === 0) {
                document.getElementById('loadingMessage').innerHTML = 
                    '<p>⚠️ No activities with valid dates found.</p>';
                return;
            }
            
            document.getElementById('loadingMessage').style.display = 'none';
            document.getElementById('ganttContainer').style.display = 'block';
            
            renderGantt(currentTasks);
        })
        .catch(err => {
            console.error(err);
            document.getElementById('loadingMessage').innerHTML = 
                '<p style="color:red;">❌ Failed to load data</p>';
        });
}

function renderGantt(tasks) {
    // Clear existing gantt
    document.getElementById('gantt').innerHTML = '';
    
    gantt = new Gantt("#gantt", tasks, {
        header_height: 50,
        column_width: 30,
        step: 24,
        view_modes: ['Day', 'Week', 'Month', 'Year'],
        bar_height: 25,
        bar_corner_radius: 3,
        arrow_curve: 5,
        padding: 18,
        view_mode: 'Week',
        date_format: 'YYYY-MM-DD',
        
        // Custom popup when clicking a bar
        custom_popup_html: function(task) {
            const critical = task.custom_class === 'critical' 
                ? '<span style="color:#dc2626;">🔴 CRITICAL</span>' : '';
            
            return `
                <div style="padding:12px; min-width:250px;">
                    <h4 style="margin-bottom:8px;">${task.name}</h4>
                    <p><strong>WBS:</strong> ${task.wbs}</p>
                    <p><strong>Duration:</strong> ${task.duration}d</p>
                    <p><strong>Float:</strong> ${task.float_days}d ${critical}</p>
                    <p><strong>Status:</strong> ${task.status}</p>
                    <p><strong>Progress:</strong> ${task.progress}%</p>
                </div>
            `;
        }
    });
}

function changeViewMode(mode) {
    if (gantt) {
        gantt.change_view_mode(mode);
        
        // Update active button
        document.querySelectorAll('.view-mode-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');
    }
}