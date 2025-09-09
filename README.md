# EHR Computer-Use Agent Extractor

A Python application that uses OpenAI's Computer-Use API to autonomously extract ICD-10 diagnoses and active medications from Practice Fusion EHR patient charts.

**Built on OpenAI CUA Sample App Architecture** - Follows established patterns and best practices from the official OpenAI Computer-Use Agent sample application.

## 🎯 What It Does

- **Autonomous EHR Navigation**: Uses AI computer vision to navigate Practice Fusion
- **Medical Data Extraction**: Extracts ICD-10 diagnoses and medication information  
- **HIPAA-Aware Safety**: Built-in safety checks for patient data handling
- **Structured Output**: Clean JSON data output saved to `ehr_extractions/`

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- OpenAI API key with Computer-Use access (tier 3+)

### 2. Setup Environment
```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate environment  
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install browsers
playwright install chromium
```

### 3. Configure API Key
Edit `.env` file:
```bash
OPENAI_API_KEY=your-api-key-here
```

### 4. Run Extraction
```bash
# Activate environment
source .venv/bin/activate

# Run extractor
# Patient id = name
python ehr_cua_extractor.py --patient-id 12345 --debug

# Results saved to: ehr_extractions/patient_12345_TIMESTAMP.json
```

## 📋 Command Options

```bash
python ehr_cua_extractor.py --patient-id PATIENT_ID [--debug] [--computer TYPE]
```

**Options:**
- `--patient-id` - Patient name to extract (required)
- `--debug` - Enable debug mode
- `--computer` - Browser type: `local-playwright`, `browserbase`, `scrapybara`

## 📁 Output

Results are saved as JSON files in `ehr_extractions/`:

```json
{
  "patient_id": "12345",
  "extraction_timestamp": "2025-09-05T10:30:00",
  "extraction_status": "success",
  "icd10_diagnoses": [
    {
      "icd10_code": "I10",
      "description": "Essential hypertension",
      "status": "active"
    }
  ],
  "active_medications": [
    {
      "name": "Lisinopril", 
      "dosage": "10mg",
      "frequency": "daily",
      "status": "active"
    }
  ]
}
```

## 🔧 Testing

```bash
# Test the setup
python test_extractor.py
```

