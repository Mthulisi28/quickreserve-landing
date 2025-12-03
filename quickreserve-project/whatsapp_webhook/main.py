import functions_framework
import json
import requests
import os
from google.cloud import firestore

# --- Configuration (Set these as Environment Variables on the Cloud Function) ---
WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN') 
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
GRAPH_API_URL = "https://graph.facebook.com/v19.0"

# Initialize Firestore client (Database)
db = firestore.Client()


def send_whatsapp_message(to_number, text_body):
    """Sends a text message using the WhatsApp Cloud API."""
    url = f"{GRAPH_API_URL}/{WHATSAPP_BUSINESS_ACCOUNT_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_body}
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp message: {e}")
        return None


@functions_framework.http
def whatsapp_webhook(request):
    """Handles both Webhook verification (GET) and incoming messages (POST)."""
    
    # 1. WEBHOOK VERIFICATION (Required by Meta)
    if request.method == 'GET':
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook Verified!")
            return challenge, 200
        else:
            print("Verification failed.")
            return 'Verification token mismatch', 403
    
    # 2. INCOMING MESSAGES (POST request)
    elif request.method == 'POST':
        try:
            data = request.get_json(silent=True)
            print(f"Received Webhook Data: {data}")
            
            if data.get('object') == 'whatsapp_business_account':
                for entry in data.get('entry', []):
                    for change in entry.get('changes', []):
                        if change.get('field') == 'messages':
                            for message in change['value']['messages']:
                                from_number = message['from']
                                
                                # Simple text message processing
                                if message['type'] == 'text':
                                    user_message = message['text']['body'].strip().lower()
                                    
                                    # --- SIMPLE KEYWORD RESPONSE LOGIC ---
                                    if 'trial' in user_message or 'free' in user_message:
                                        response_text = "Awesome! To start your free trial, we'll need to check availability. Please reply with the date and time you prefer (e.g., 'Wed 3pm')."
                                    elif 'book' in user_message:
                                        response_text = "Got it. To book, please reply with the service name and preferred date/time."
                                    else:
                                        response_text = "Hello! I'm QuickReserve's automated assistant. Reply 'TRIAL' to start your free trial, or 'HELP' for human assistance."
                                    
                                    send_whatsapp_message(from_number, response_text)
                                    
            return 'OK', 200

        except Exception as e:
            print(f"Error processing webhook: {e}")
            return 'OK', 200 # Always return 200 to Meta
    
    return 'Method Not Allowed', 405