# AI Extension Framework for ERPNext

A Frappe v15 app for assigning assistants to ERPNext forms. Open **AI Extensions → AI Feature Dashboard** as a System Manager. Choose a feature and switch on a compatible module or form. Form overrides take precedence. **Use default** restores module inheritance. Open the linked form list, choose a record, then open **Actions** to use the feature.

| Assistant | Available on | What it does |
| --- | --- | --- |
| Duplicate Finder | Lead, Customer, Supplier, Item | Ranks possible matches using names and identifiers. Works before saving. |
| CRM Handoff Brief | Lead, Opportunity | Summarizes the saved stage, accessible open tasks and selected CRM note excerpts, with links to the sources. |
| Purchase Invoice Review | Purchase Invoice | Compares this invoice’s billed quantities and unit prices with explicitly linked purchase order and receipt rows. |
| Similar Issue Finder | Issue | Searches accessible resolved and closed cases, ranks matching symptoms and shows the recorded resolution. |
| AI Chat Assistant | ERPNext document forms | Opens a demonstration chat with form context. |
| AI Form Assistant | Lead, Purchase Receipt | Extracts draft values from attachments using Azure Document Intelligence and OpenAI. |

The four review and search tools run locally. CRM Handoff Brief also offers **Draft handoff with OpenAI** when credentials and source notes or tasks are available. Clicking that button sends the displayed excerpts to the configured account. Reviews and drafts do not update or submit business documents.

Feature assignments are stored per site. New installations start with Form Assistant on its mapped forms and the other features opt-in. Each feature declares its compatible DocTypes in the extension catalog. Source access follows the current user’s Frappe permissions.

## Lead extraction walkthrough

The original screenshots below show the earlier **AI Assist** button. The current entry point is **Actions → AI Form Assistant**.

## Demo Video

🎥 Watch the project demonstration here:

**Google Drive:**  
https://drive.google.com/file/d/1Xu3gFgqrpi4maC38-51Wscgai0J9Vk9-/view?usp=sharing

## Features

- AI Assist button integrated into the Lead form
- OCR-based information extraction
- Automatic Lead field population
- Modular service-oriented architecture
- Built as a custom Frappe application
- Upgrade-safe (no ERPNext core modifications)

---

# How it Works

### Step 1 - Attach the ID Document

Upload an ID document (business card, ID card, or similar document) to the **ID Document** field on the Lead form.

<p align="center">
  <img src="screenshots/step1-upload-document.png" width="900">
</p>

---

### Step 2 - Click **AI Assist**

Click the **AI Assist** button to extract information from the uploaded document.

<p align="center">
  <img src="screenshots/step2-ai-assist.png" width="900">
</p>

---

### Step 3 - Review & Save

The extracted information is automatically populated into the Lead fields. Review the generated values and save the Lead.

<p align="center">
  <img src="screenshots/step3-autofill.png" width="900">
</p>
## Technology Stack

- ERPNext v15
- Frappe Framework v15
- Python
- JavaScript (Client Scripts)
- OCR

---

## Architecture

```
Lead Form
     │
     ▼
AI Assist Button
     │
     ▼
Client Script
     │
     ▼
Whitelisted API
     │
     ▼
Lead Service
     │
     ▼
File Service
     │
     ▼
OCR Service
     │
     ▼
Populate Lead Fields
```

---

## Project Structure

```
ai_lead_assistant/
├── api.py
├── hooks.py
├── public/
│   └── js/
├── services/
│   ├── lead_service.py
│   ├── file_service.py
│   └── ocr_service.py
```

---

## Future Improvements

- Duplicate Lead Detection
- AI-based Lead Scoring
- Suggested Sales Representative
- Suggested Industry & Territory
- Confidence Score for AI Predictions
- Batch Lead Creation from Multiple Documents

---

## Installation

Clone the repository into your Frappe Bench.

```bash
cd frappe-bench

bench get-app https://github.com/<your-github-username>/AI-Lead-Assistant.git

bench --site <site-name> install-app ai_lead_assistant

bench migrate
```

---

## License

This project is licensed under the MIT License.