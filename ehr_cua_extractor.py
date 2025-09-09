#!/usr/bin/env python3
"""
EHR Computer-Use Agent (CUA) Extractor

A visual computer-use agent for extracting ICD-10 diagnoses and medications from any EHR system.
Uses pure computer vision - no DOM selectors, works with web apps and native applications.

Usage:
    python ehr_cua_extractor.py --patient-id "John Smith"
    python ehr_cua_extractor.py --patient-id "Jane Doe" --debug
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

# Import local agent and computer modules
try:
    from agent import Agent
    from computers.default.local_playwright import LocalPlaywrightBrowser
    from computers.default.browserbase import BrowserbaseBrowser
    from computers.default.scrapybara import ScrapybaraBrowser
except ImportError as e:
    print(f"❌ Error importing CUA components: {e}")
    print("📁 Make sure the agent/ and computers/ folders are present in this directory")
    print("💡 These should have been copied from the OpenAI CUA sample app")
    sys.exit(1)


class EHRExtractor:
    """
    Universal EHR Computer Use Agent for visual data extraction.
    
    Uses pure computer vision to work with any EHR system - web apps or native applications.
    No DOM selectors or HTML inspection - relies entirely on visual recognition.
    """
    
    def __init__(self, computer_type: str = "local-playwright", debug: bool = False):
        self.computer_type = computer_type
        self.debug = debug
        self.extraction_results = {
            "patient_id": None,
            "extraction_timestamp": datetime.now().isoformat(),
            "icd10_diagnoses": [],
            "active_medications": [],
            "extraction_status": "pending",
            "metadata": {
                "computer_type": computer_type,
                "debug_mode": debug
            }
        }
        
        # Define EHR-specific tools following sample app function patterns
        self.ehr_tools = [
            {
                "type": "function",
                "name": "navigate_to_patient",
                "description": "Navigate to a specific patient's chart in the EHR system",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "string",
                            "description": "The patient ID or identifier to navigate to"
                        },
                        "success": {
                            "type": "boolean",
                            "description": "Whether navigation was successful"
                        }
                    },
                    "required": ["patient_id", "success"]
                }
            },
            {
                "type": "function", 
                "name": "record_diagnoses",
                "description": "Record ICD-10 diagnoses found in the patient chart",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "diagnoses": {
                            "type": "array",
                            "description": "List of ICD-10 diagnoses found",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "icd10_code": {"type": "string", "description": "ICD-10 code (e.g., Z00.00)"},
                                    "description": {"type": "string", "description": "Human readable diagnosis description"},
                                    "status": {"type": "string", "description": "Status (active, resolved, etc.)"},
                                    "date": {"type": "string", "description": "Date of diagnosis if available"}
                                },
                                "required": ["icd10_code", "description"]
                            }
                        }
                    },
                    "required": ["diagnoses"]
                }
            },
            {
                "type": "function",
                "name": "record_medications", 
                "description": "Record active medications found in the patient chart",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "medications": {
                            "type": "array",
                            "description": "List of active medications found",
                            "items": {
                                "type": "object", 
                                "properties": {
                                    "name": {"type": "string", "description": "Medication name"},
                                    "dosage": {"type": "string", "description": "Dosage amount and unit"},
                                    "frequency": {"type": "string", "description": "How often taken"},
                                    "route": {"type": "string", "description": "Route of administration"},
                                    "status": {"type": "string", "description": "Status (active, discontinued, etc.)"},
                                    "prescriber": {"type": "string", "description": "Prescribing provider if available"}
                                },
                                "required": ["name"]
                            }
                        }
                    },
                    "required": ["medications"]
                }
            },
            {
                "type": "function",
                "name": "complete_extraction",
                "description": "Mark the extraction as complete and save results",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "description": "Whether extraction was successful"},
                        "summary": {"type": "string", "description": "Summary of what was extracted"},
                        "total_diagnoses": {"type": "integer", "description": "Total number of diagnoses found"},
                        "total_medications": {"type": "integer", "description": "Total number of medications found"}
                    },
                    "required": ["success", "summary"]
                }
            }
        ]
    
    def _get_computer(self):
        """Get computer instance based on type (following sample app patterns)"""
        computers = {
            "local-playwright": lambda: LocalPlaywrightBrowser(headless=False),
            "browserbase": BrowserbaseBrowser,
            "scrapybara": ScrapybaraBrowser
        }
        
        if self.computer_type not in computers:
            raise ValueError(f"Unsupported computer type: {self.computer_type}. Available: {list(computers.keys())}")
        
        return computers[self.computer_type]()
    
    def _ehr_safety_callback(self, message: str) -> bool:
        """Custom safety callback for EHR operations with HIPAA considerations"""
        print(f"\n🔒 EHR Safety Check: {message}")
        
        # Special handling for patient data access
        sensitive_terms = ["patient data", "phi", "hipaa", "medical record", "chart"]
        if any(term in message.lower() for term in sensitive_terms):
            print("⚠️  This operation involves protected health information (PHI).")
            print("📋 Ensure you have:")
            print("   - Proper authorization to access this patient's data")
            print("   - Compliance with HIPAA regulations") 
            print("   - Appropriate security measures in place")
            
            response = input("✅ Do you confirm authorization and compliance? (y/n): ")
            return response.lower().strip() == 'y'
        
        # Standard safety check
        response = input("🤔 Do you want to proceed with this action? (y/n): ")
        return response.lower().strip() == 'y'
    
    def _create_agent(self, computer) -> Agent:
        """Create agent with EHR-specific tools and safety measures"""
        agent = Agent(
            model="computer-use-preview",
            computer=computer,
            tools=self.ehr_tools,
            acknowledge_safety_check_callback=self._ehr_safety_callback
        )
        
        # Override the agent's handle_item method to route our custom functions
        original_handle_item = agent.handle_item
        
        def custom_handle_item(item):
            if item.get("type") == "function_call":
                name = item.get("name")
                args = json.loads(item.get("arguments", "{}"))
                call_id = item.get("call_id")
                
                if agent.print_steps:
                    print(f"🔧 {name}({args})")
                
                # Route our custom EHR functions to the EHRExtractor methods
                if name == "navigate_to_patient":
                    result = self.navigate_to_patient(args.get("patient_id"), args.get("success"))
                elif name == "record_diagnoses":
                    result = self.record_diagnoses(args.get("diagnoses", []))
                elif name == "record_medications":
                    result = self.record_medications(args.get("medications", []))
                elif name == "complete_extraction":
                    result = self.complete_extraction(
                        args.get("success"), 
                        args.get("summary"), 
                        args.get("total_diagnoses"), 
                        args.get("total_medications")
                    )
                else:
                    # Fall back to original handler for computer functions
                    return original_handle_item(item)
                
                return [{
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result)
                }]
            else:
                # For non-function calls, use original handler
                return original_handle_item(item)
        
        # Replace the agent's handle_item method
        agent.handle_item = custom_handle_item
        return agent
    
    # Custom function implementations (called by the agent)
    def navigate_to_patient(self, patient_id: str, success: bool) -> Dict:
        """Handle patient navigation function call"""
        self.extraction_results["patient_id"] = patient_id
        if success:
            print(f"✅ Successfully navigated to patient {patient_id}")
        else:
            print(f"❌ Failed to navigate to patient {patient_id}")
        return {"status": "recorded", "patient_id": patient_id}
    
    def record_diagnoses(self, diagnoses: List[Dict]) -> Dict:
        """Handle diagnoses recording function call"""
        self.extraction_results["icd10_diagnoses"] = diagnoses
        count = len(diagnoses)
        print(f"🩺 Recorded {count} ICD-10 diagnoses:")
        for diag in diagnoses:
            code = diag.get('icd10_code', 'Unknown')
            desc = diag.get('description', 'No description')
            print(f"   • {code}: {desc}")
        return {"status": "recorded", "count": count}
    
    def record_medications(self, medications: List[Dict]) -> Dict:
        """Handle medication recording function call"""
        self.extraction_results["active_medications"] = medications
        count = len(medications)
        print(f"💊 Recorded {count} active medications:")
        for med in medications:
            name = med.get('name', 'Unknown')
            dosage = med.get('dosage', '')
            status = med.get('status', 'unknown')
            print(f"   • {name} {dosage} ({status})")
        return {"status": "recorded", "count": count}
    
    def complete_extraction(self, success: bool, summary: str, 
                          total_diagnoses: Optional[int] = None, total_medications: Optional[int] = None) -> Dict:
        """Handle extraction completion function call"""
        self.extraction_results["extraction_status"] = "success" if success else "failed"
        
        # Update counts if provided
        if total_diagnoses is not None:
            expected_diag = len(self.extraction_results["icd10_diagnoses"])
            if expected_diag != total_diagnoses:
                print(f"⚠️  Diagnosis count mismatch: recorded {expected_diag}, expected {total_diagnoses}")
        
        if total_medications is not None:
            expected_med = len(self.extraction_results["active_medications"])
            if expected_med != total_medications:
                print(f"⚠️  Medication count mismatch: recorded {expected_med}, expected {total_medications}")
        
        # Save results to file
        output_path = self._save_results()
        
        print(f"\n📊 Extraction Complete:")
        print(f"   Status: {'✅ Success' if success else '❌ Failed'}")
        print(f"   Summary: {summary}")
        print(f"   File: {output_path}")
        
        return {"status": "completed", "output_path": str(output_path)}
    
    def _save_results(self) -> Path:
        """Save extraction results to JSON file"""
        # Create output directory
        output_dir = Path("./ehr_extractions")
        output_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp and patient ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patient_id = self.extraction_results.get("patient_id", "unknown")
        filename = f"patient_{patient_id}_{timestamp}.json"
        
        output_path = output_dir / filename
        
        with open(output_path, 'w') as f:
            json.dump(self.extraction_results, f, indent=2)
        
        return output_path
    
    def extract_patient_data(self, patient_id: str, start_url: Optional[str] = None):
        """
        Main extraction workflow using Agent pattern from CUA sample app
        """
        start_url = start_url or os.getenv('START_URL', 'https://static.practicefusion.com/apps/ehr/#/login')
        
        print(f"🚀 EHR CUA Extractor Starting")
        print(f"   Patient ID: {patient_id}")
        print(f"   Computer: {self.computer_type}")
        print(f"   Debug Mode: {self.debug}")
        print(f"   Start URL: {start_url}")
        
        with self._get_computer() as computer:
            agent = self._create_agent(computer)
            
            # Navigate to EHR URL first (like the openai-cua-sample-app does)
            print(f"🌐 Navigating to EHR system: {start_url}")
            try:
                computer.goto(start_url)
                print(f"✅ Successfully navigated to {start_url}")
            except Exception as e:
                print(f"❌ Failed to navigate to {start_url}: {e}")
                print("🔄 Continuing anyway - agent will try to navigate...")
            
            # Create initial conversation with comprehensive instructions
            items = [
                {
                    "role": "developer",
                    "content": f"""You are an EHR Data Extraction Specialist using computer vision to extract structured medical data.

MISSION: Extract ICD-10 diagnoses and active medications for patient ID: {patient_id}

You are now on the EHR system page. Continue with the workflow below:

WORKFLOW - Visual Navigation Only:
1. Complete authentication (ask user for help if needed)
2. Look for and click "Charts" or similar navigation element in the interface
3. Find and use patient search functionality
4. Search for patient by name: "{patient_id}" (this is actually a patient name, not ID)
5. Click on the patient name/row to open their chart
6. Once on patient chart, visually identify and extract data sections:
   - Find "Medications", "Meds", or "Active Medications" section
   - Find "Diagnoses", "Problems", "ICD", or "Conditions" section
7. Use the provided functions to record your findings

IMPORTANT FUNCTIONS TO USE:
- navigate_to_patient(patient_id, success): Call when you reach the patient's chart
- record_diagnoses(diagnoses): Record all ICD-10 diagnoses found
- record_medications(medications): Record all active medications found  
- complete_extraction(success, summary): Call when extraction is complete

VISUAL IDENTIFICATION GUIDELINES:
You must rely ONLY on visual recognition - no DOM inspection or selectors allowed.

For Medications Section:
- Look for headings containing: "Medication", "Meds", "Active Medications", "Current Medications"
- Identify medication lists visually - typically formatted as:
  • Medication Name + Dosage (e.g., "Lisinopril 10mg")
  • May include frequency (daily, BID, etc.)
  • May show status indicators (Active, Discontinued, etc.)
- Parse medication entries to extract: name, dosage, frequency, status

For Diagnoses/ICD Section:
- Look for headings containing: "Diagnoses", "Problems", "Conditions", "ICD", "ICD-10"
- Identify diagnosis lists visually - typically formatted as:
  • ICD code in parentheses + description (e.g., "(I10) Essential hypertension")
  • Or description followed by code
  • May include dates, status indicators
- Parse entries to extract: ICD-10 code, description, status

EXTRACTION REQUIREMENTS:
- Use ONLY computer vision - do not inspect DOM elements or use selectors
- Look for visual patterns, headings, and layout cues
- Scroll through sections if needed to find all data
- If sections are empty, record empty arrays but note this in your summary

SAFETY NOTES:
- This involves protected health information (PHI)
- Only access data you're authorized to view
- Handle data securely and privately
- If authentication is required, ask the user to complete it

CRITICAL INSTRUCTION - VISUAL ONLY:
You MUST rely entirely on computer vision and visual recognition. DO NOT:
- Inspect DOM elements or HTML
- Use CSS selectors or XPath
- Look at page source or developer tools
- Use any programmatic element identification

Instead, you MUST:
- Read text visually on screen like a human would
- Look for visual patterns, headers, and section layouts
- Use click coordinates based on what you see
- Scroll and navigate based on visual interface elements
- Parse medication and diagnosis information by reading the displayed text

VISUAL PARSING EXAMPLES:
Medications might appear as:
- "Lisinopril 10mg daily" → name="Lisinopril", dosage="10mg", frequency="daily"
- "Metformin 500mg BID (Active)" → name="Metformin", dosage="500mg", frequency="BID", status="Active"

Diagnoses might appear as:
- "(I10) Essential hypertension" → code="I10", description="Essential hypertension"
- "Type 2 diabetes mellitus (E11.9)" → code="E11.9", description="Type 2 diabetes mellitus"
- "Essential hypertension - I10" → code="I10", description="Essential hypertension"

Begin by examining the current page to see what EHR interface elements are visible. Look for login fields, navigation menus, or patient search functionality."""
                }
            ]
            
            # Execute the extraction workflow using agent
            try:
                print("\n🤖 Starting agent-driven extraction...")
                
                # Start interactive conversation loop (like the openai-cua-sample-app CLI)
                while True:
                    # Run the full conversation turn
                    output_items = agent.run_full_turn(
                        items, 
                        print_steps=True, 
                        debug=self.debug, 
                        show_images=False  # Never show screenshots, even in debug mode
                    )
                    
                    # Add the agent's response to the conversation
                    items.extend(output_items)
                    
                    # Check if extraction is complete
                    if self.extraction_results.get("extraction_status") in ["success", "failed"]:
                        print(f"\n✅ Agent workflow completed")
                        return self.extraction_results
                    
                    # Get user input for next step (credentials, confirmations, etc.)
                    try:
                        user_input = input("\n👤 Your response (or 'exit' to quit): ")
                        if user_input.lower().strip() == 'exit':
                            print("🛑 Extraction stopped by user")
                            self.extraction_results["extraction_status"] = "interrupted"
                            return self.extraction_results
                        
                        # Add user input to conversation
                        items.append({"role": "user", "content": user_input})
                        
                    except EOFError:
                        print("\n🛑 Input ended, stopping extraction")
                        self.extraction_results["extraction_status"] = "interrupted"
                        return self.extraction_results
                
            except KeyboardInterrupt:
                print(f"\n⏹️  Extraction interrupted by user")
                self.extraction_results["extraction_status"] = "interrupted"
                return self.extraction_results
                
            except Exception as e:
                print(f"\n❌ Extraction failed with error: {e}")
                self.extraction_results["extraction_status"] = "failed"
                self.extraction_results["error"] = str(e)
                return self.extraction_results


def main():
    """CLI interface following OpenAI CUA sample app patterns"""
    parser = argparse.ArgumentParser(
        description="EHR Computer-Use Agent Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ehr_cua_extractor.py --patient-id "John Smith"
  python ehr_cua_extractor.py --patient-id "Jane Doe" --debug
  python ehr_cua_extractor.py --patient-id "Robert Johnson" --computer browserbase
  
Note: This extractor uses pure computer vision - works with web EHR systems and native apps
  
Environment Variables:
  OPENAI_API_KEY     Required: Your OpenAI API key with Computer Use access
  START_URL          Optional: EHR login URL (defaults to Practice Fusion)
        """
    )
    
    parser.add_argument(
        "--patient-id",
        required=True,
        help="Patient name to search for (uses visual search, works with any EHR system)"
    )
    parser.add_argument(
        "--computer", 
        choices=["local-playwright", "browserbase", "scrapybara"],
        default="local-playwright",
        help="Computer environment to use (default: local-playwright)"
    )
    parser.add_argument(
        "--start-url",
        help="EHR login URL (defaults to Practice Fusion from env or hardcoded)"
    )
    parser.add_argument(
        "--debug",
        action="store_true", 
        help="Enable debug mode with screenshots and detailed logging"
    )
    
    args = parser.parse_args()
    
    # Validate environment
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY environment variable is required")
        print("💡 Get your API key from: https://platform.openai.com/account/api-keys")
        sys.exit(1)
    
    print("🔧 EHR CUA Extractor v2.0")
    print("📋 Based on OpenAI Computer-Use Agent Sample App")
    
    # Create extractor instance
    try:
        extractor = EHRExtractor(
            computer_type=args.computer,
            debug=args.debug
        )
    except Exception as e:
        print(f"❌ Failed to initialize extractor: {e}")
        sys.exit(1)
    
    # Execute extraction
    results = extractor.extract_patient_data(
        patient_id=args.patient_id,
        start_url=args.start_url
    )
    
    # Print final summary
    print(f"\n" + "="*60)
    print(f"📊 EXTRACTION SUMMARY")
    print(f"="*60)
    print(f"Patient ID:       {results.get('patient_id', 'Unknown')}")
    print(f"Status:           {results.get('extraction_status', 'Unknown')}")
    print(f"ICD-10 Diagnoses: {len(results.get('icd10_diagnoses', []))}")
    print(f"Active Meds:      {len(results.get('active_medications', []))}")
    print(f"Timestamp:        {results.get('extraction_timestamp', 'Unknown')}")
    
    if results.get('extraction_status') == 'success':
        print(f"✅ Extraction completed successfully!")
        exit_code = 0
    else:
        error_msg = results.get('error', 'Unknown error occurred')
        print(f"❌ Extraction failed: {error_msg}")
        exit_code = 1
    
    print(f"="*60)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
