from flask import Flask, request, jsonify
import socket
import requests
import json
import firebase_admin
from firebase_admin import credentials, db
import threading
import time

app = Flask(__name__)

PI_A_IP = '192.255.0.2'
PI_B_IP = '192.255.0.3'
PI_A_PORT = 5000
PI_B_PORT = 5000

# Initialize Firebase
# cred = credentials.Certificate("privateKey.json")
# firebase_admin.initialize_app(cred)
cred = credentials.Certificate("privateKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smartpicklocker-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

def poll_firebase():
    while True:
        try:
            ref = db.reference('/Deliveries')
            parcels = ref.get()

            for parcel_id, info in parcels.items():
                status = info.get("status")
                if status == "Unlocked":
                    locker = info.get("locker")
                    pin = info.get("pin")

                    print(f"[{parcel_id}] Unlocking locker {locker} with PIN {pin}")

                    response = requests.post(f"{PI_A_IP}:{PI_A_PORT}/unlock", json={
                    "parcel_id": parcel_id,
                    "locker": locker,
                    "pin": pin
                })
                
                    if response.status_code == 200:
                        print(f"Unlock command sent to PI A for {parcel_id}")

                        # Update the status to avoid repeat triggers
                        ref.child(parcel_id).update({"status": "Collected"})

                    
        except Exception as e:
            print(f"Error polling Firebase: {e}")

        time.sleep(2)  # Poll every 5 seconds

# Start polling in a background thread
def start_polling():
    poll_thread = threading.Thread(target=poll_firebase)
    poll_thread.daemon = True
    poll_thread.start()

# Flask basic route
# @app.route('/health', methods=['GET'])
# def health():
#     return jsonify({"status": "Server is running"}), 200

@app.route('/unlock_locker', methods=['POST'])
def unlock_locker():
    data = request.get_json()
    print("Received:", data)

    parcel_id = data.get('parcel_id')

    if not parcel_id:
        return jsonify({'error': 'Missing parcel ID'}), 400
    
    #Forward to PI A via TCP socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((PI_A_IP, PI_A_PORT))
            message = json.dumps({'parcel_id': parcel_id})
            s.sendall(message.encode('utf-8'))
        return jsonify({'message': 'Unlock command forwarded to Pi A'}), 200
    
    except Exception as e:
        print(f"error forwarding to Pi A: {e}")
        return jsonify({'error': 'Failed to forward to lcoker controller'}), 500
    
@app.route('/syn', methods=['GET'])
def syn():
    print('SYN received. Sending SYN-ACK...')
    return jsonify({'status': 'SYN-ACK'}), 200

@app.route('/ack', methods=['POST'])
def ack():
    data = request.get_json()
    if data and data.get('ack') == 'ACK':
        print('ACK received from client. Handshake complete.')
        return jsonify({'status': 'Handshake complete'}), 200
    return jsonify({'error': 'Invalid ACK'}), 400

if __name__ == '__main__':
    start_polling()
    app.run(host='0.0.0.0', port = 5000)