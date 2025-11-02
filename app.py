from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import json
import boto3
import random
import traceback

app = Flask(__name__, static_folder='static')
CORS(app)

s3_client = boto3.client('s3')
bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')

S3_BUCKET_NAME = 'sh2025-crai-tech-data-universe'
TICKETS_FILE_KEY = 'tickets.json'
ALERTS_FILE_KEY = 'alerts.json'
ASSETS_FILE_KEY = 'assets.json'

# --- HELPER FUNCTIONS ---
def get_ticket_by_id(ticket_id):
    try:
        s3_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=TICKETS_FILE_KEY)
        all_tickets = json.loads(s3_object['Body'].read().decode('utf-8'))
        for ticket in all_tickets:
            if ticket.get('id') == ticket_id: return ticket
        return None
    except Exception: return None

def get_asset_details_by_id(asset_id):
    try:
        s3_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=ASSETS_FILE_KEY)
        all_assets = json.loads(s3_object['Body'].read().decode('utf-8'))
        return all_assets.get(asset_id, None)
    except Exception as e: return None

def find_related_alerts(asset_id):
    try:
        s3_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=ALERTS_FILE_KEY)
        all_alerts = json.loads(s3_object['Body'].read().decode('utf-8'))
        return [a for a in all_alerts if a.get('asset_id') == asset_id]
    except Exception: return []

def get_ai_analysis_from_bedrock(ticket_description, alerts):
    alerts_str = json.dumps(alerts) if alerts else "No alerts found."
    prompt = f"""Human: You are an expert Level 2 IT Support Engineer. Your task is to analyze an incoming support ticket and associated system alerts to provide a comprehensive action plan for the Level 1 technician.
Here is the data you have:
## User Ticket Description:
"{ticket_description}"
## Real-time Monitoring Alerts:
{alerts_str}
Based on all of this information, provide your analysis in a structured JSON format. The JSON object must have exactly these three keys:
1. "summary": A detailed, 2-3 sentence summary of the user's problem and its likely impact.
2. "probable_root_cause": Your expert opinion on the single most likely root cause of the issue.
3. "recommended_steps": A JSON array of 3 to 5 concrete, actionable steps the technician should take to investigate and resolve the problem.
Assistant:
```json
"""
    body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]})
    model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'
    try:
        response = bedrock_runtime.invoke_model(body=body, modelId=model_id, accept='application/json', contentType='application/json')
        response_body = json.loads(response.get('body').read())
        
        # THIS IS THE CORRECT, VERIFIED, FINAL FIX FOR THE TypeError
        ai_json_string = response_body['content'][0]['text'].replace("```json", "").replace("```", "")
        
        ai_analysis = json.loads(ai_json_string)
        return ai_analysis
    except Exception as e:
        traceback.print_exc()
        return {"summary": "AI analysis failed. Check logs.", "probable_root_cause": "N/A", "recommended_steps": ["Check the server logs for a detailed traceback."]}

# --- ROUTES ---
@app.route('/')
def serve_agent_view(): return send_from_directory(app.static_folder, 'index.html')

@app.route('/script.js')
def serve_js(): return send_from_directory(app.static_folder, 'script.js')

@app.route('/create')
def serve_create_ticket_page(): return send_from_directory(app.static_folder, 'create-ticket.html')

@app.route('/analyze/<ticket_id>', methods=['GET'])
def analyze_ticket(ticket_id):
    ticket = get_ticket_by_id(ticket_id)
    if not ticket: return jsonify({"error": "Ticket not found"}), 404
    asset_id = ticket.get('asset_id')
    asset_details = get_asset_details_by_id(asset_id)
    related_alerts = find_related_alerts(asset_id)
    ai_analysis = get_ai_analysis_from_bedrock(ticket['description'], related_alerts)
    response_data = {"ticket": ticket, "ai_analysis": ai_analysis, "related_alerts": related_alerts, "asset_details": asset_details}
    return jsonify(response_data)

@app.route('/create-ticket', methods=['POST'])
def create_ticket():
    data = request.json
    if not data or 'asset_id' not in data or 'description' not in data or 'client_id' not in data:
        return jsonify({'error': 'Missing data'}), 400
    try:
        s3_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=TICKETS_FILE_KEY)
        all_tickets = json.loads(s3_object['Body'].read().decode('utf-8'))
        new_id = "TKT" + str(random.randint(100, 999))
        new_ticket = {"id": new_id, "subject": data['description'][:50] + '...', "description": data['description'], "client_id": data['client_id'], "asset_id": data['asset_id'], "status": "New"}
        all_tickets.append(new_ticket)
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=TICKETS_FILE_KEY, Body=json.dumps(all_tickets, indent=2), ContentType='application/json')
        return jsonify({'success': True, 'new_ticket_id': new_id})
    except Exception as e: return jsonify({'error': str(e)}), 500
    
@app.route('/history/<client_id>', methods=['GET'])
def get_user_history(client_id):
    try:
        s3_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=TICKETS_FILE_KEY)
        all_tickets = json.loads(s3_object['Body'].read().decode('utf-8'))
        user_tickets = [ticket for ticket in all_tickets if ticket.get('client_id') == client_id]
        return jsonify(user_tickets)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@app.route('/ticket/<ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    data = request.json
    new_status = data.get('status')
    if not new_status: return jsonify({'error': 'New status not provided'}), 400
    try:
        s3_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=TICKETS_FILE_KEY)
        all_tickets = json.loads(s3_object['Body'].read().decode('utf-8'))
        ticket_found = False
        for ticket in all_tickets:
            if ticket.get('id') == ticket_id:
                ticket['status'] = new_status
                ticket_found = True
                break
        if not ticket_found: return jsonify({'error': 'Ticket ID not found'}), 404
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=TICKETS_FILE_KEY, Body=json.dumps(all_tickets, indent=2), ContentType='application/json')
        return jsonify({'success': True, 'message': f'Ticket {ticket_id} status updated to {new_status}'})
    except Exception as e: return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
