"""
UNIVERSAL SCHEDULE PARSER
=========================
Detects file type (.xer, P6 .xml, MSP .xml) and routes to the appropriate parser.
Returns standard XER dictionary structure regardless of input format.
"""

from parser import XERParser
from p6_xml_parser import P6XMLParser
from msp_xml_parser import MSPXMLParser
import logging

logger = logging.getLogger(__name__)

class UniversalParser:
    def parse(self, stream, filename):
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if ext == 'xer':
            logger.info("Routing to XER Parser")
            return XERParser().parse(stream)
            
        elif ext == 'xml':
            # Peak at first few lines to differentiate P6 XML vs MSP XML
            try:
                head = stream.read(1024)
                if isinstance(head, bytes):
                    head_str = head.decode('utf-8', errors='ignore')
                else:
                    head_str = head
                stream.seek(0)  # Reset stream position
                
                if 'schemas.microsoft.com/project' in head_str:
                    logger.info("Routing to MSP XML Parser")
                    return MSPXMLParser().parse(stream)
                else:
                    logger.info("Routing to P6 XML Parser")
                    return P6XMLParser().parse(stream)
            except Exception as e:
                logger.error(f"Failed to detect XML schema: {e}")
                return None
                
        else:
            logger.error(f"Unsupported file format: {ext}")
            return None
