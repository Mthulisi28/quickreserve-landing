import functions_framework
from google.cloud import firestore
import requests
import os
from datetime import datetime, timedelta
import pytz 

# --- Configuration (Set these as Environment Variables) ---
WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN') 
GRAPH_API_URL = "https://graph.facebook.com/v19.0"
SAST = pytz.timezone('Africa/Johannesburg') # South Africa Standard Time

# Initialize Firestore client
db = firestore.Client()
BOOKINGS_COLLECTION = 'appointments'


def send_whatsapp_template_reminder(to_number, customer_name, service_time):
    """
    Sends a pre-approved template message (required for proactive messages)
    NOTE: You MUST create an approved 'appointment_reminder' template in Meta Business Manager
    """
    url = f"{GRAPH_API_URL}/{WHATSAPP_BUSINESS_ACCOUNT_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "appointment_reminder", # Use your actual approved template name
            "language": {"code": "en"}, # Assuming English template
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": customer_name},
                        {"type": "text", "text": service_time}
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print(f"Reminder sent to {to_number}: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending template message to {to_number}: {e}")


@functions_framework.http
def send_reminders(request):
    """Queries Firestore for tomorrow's appointments and sends reminders."""
    
    # 1. Define the date range for tomorrow in SAST
    now_sast = datetime.now(SAST)
    tomorrow_start_sast = SAST.localize(datetime(now_sast.year, now_sast.month, now_sast.day, 0, 0, 0) + timedelta(days=1))
    tomorrow_end_sast = tomorrow_start_sast + timedelta(days=1)
    
    print(f"Searching for appointments between {tomorrow_start_sast} and {tomorrow_end_sast}")

    # 2. Query Firestore 
    query = db.collection(BOOKINGS_COLLECTION) \
        .where('appointment_time', '>=', tomorrow_start_sast) \
        .where('appointment_time', '<', tomorrow_end_sast) \
        .where('status', '==', 'confirmed') \
        .stream()

    reminders_sent = 0
    for doc in query:
        data = doc.to_dict()
        phone_number = data.get('phone')
        customer_name = data.get('name', 'Client')
        
        # Convert the Firestore timestamp to a readable SAST string for the message
        appointment_time_utc = data.get('appointment_time').replace(tzinfo=pytz.utc)
        appointment_time_sast = appointment_time_utc.astimezone(SAST)
        service_time_str = appointment_time_sast.strftime('%A, %d %B at %H:%M') # e.g., "Tuesday, 03 December at 15:00"
        
        if phone_number:
            send_whatsapp_template_reminder(
                to_number=phone_number,
                customer_name=customer_name,
                service_time=service_time_str
            )
            reminders_sent += 1

    return f'Reminder process complete. {reminders_sent} reminders attempted.', 200