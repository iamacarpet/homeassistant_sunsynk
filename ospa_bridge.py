import tinytuya
import json
import sys
import time
import os
import queue
import threading
import select
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# --- CONFIGURATION ---
CONFIG_FILE = 'config.json'
HTTP_PORT = 8883
HEARTBEAT_INTERVAL = 9  # Seconds (Tuya usually times out > 15s)

# --- GLOBAL SHARED STATE ---
data_lock = threading.Lock()
LATEST_DATA = {
    "status": "initializing",
    "timestamp": 0,
    "error": None,
    "data": {}
}

# Queue for write commands from HTTP handler → Tuya worker thread
# Each item: {"dps": {"1": True, "2": "heating", ...}}
command_queue = queue.Queue()

# --- DATA MAPPING (DP ID to sections/slugs) ---
dp_map = {
    '1':  {'section': 'system', 'slug': 'power_on',           'scale': 1},
    '2':  {'section': 'system', 'slug': 'mode',               'scale': 1},
    '17': {'section': 'system', 'slug': 'work_state',         'scale': 1},
    '15': {'section': 'system', 'slug': 'fault_bitmap',       'scale': 1},
    '4':  {'section': 'temperatures', 'slug': 'target_temp_c',      'scale': 10},
    '16': {'section': 'temperatures', 'slug': 'current_temp_c',     'scale': 10},
    '23': {'section': 'temperatures', 'slug': 'coil_temp_c',        'scale': 10},
    '24': {'section': 'temperatures', 'slug': 'exhaust_temp_c',     'scale': 10},
    '26': {'section': 'temperatures', 'slug': 'ambient_temp_c',     'scale': 10},
    '27': {'section': 'components', 'slug': 'compressor_active', 'scale': 1},
    '28': {'section': 'components', 'slug': 'four_way_valve',    'scale': 1},
    '29': {'section': 'components', 'slug': 'fan_active',        'scale': 1},
    '30': {'section': 'components', 'slug': 'water_pump_active', 'scale': 1},
    '32': {'section': 'components', 'slug': 'elec_heat_active',  'scale': 1},
    '7':  {'section': 'components', 'slug': 'defrost_active',    'scale': 1},
    '33': {'section': 'components', 'slug': 'defrost_state',     'scale': 1},
    '108':{'section': 'components', 'slug': 'antifreeze_active', 'scale': 1},
    '102': {'section': 'diagnostics', 'slug': 'eev_step_count',  'scale': 1},
    '103': {'section': 'manual', 'slug': 'heat_mode',            'scale': 1},
    '104': {'section': 'manual', 'slug': 'pump_mode',            'scale': 1},
}


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        log(f"CRITICAL: {CONFIG_FILE} not found.")
        sys.exit(1)
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        log(f"Config Error: {e}")
        sys.exit(1)


def process_raw_dps(raw_dps):
    clean_data = {
        "system": {},
        "temperatures": {},
        "components": {},
        "diagnostics": {},
        "manual": {},
        "unknown": {}
    }
    for dp_id, value in raw_dps.items():
        dp_id = str(dp_id)
        if dp_id in dp_map:
            mapping = dp_map[dp_id]
            section = mapping['section']
            slug = mapping['slug']
            scale = mapping['scale']
            if scale > 1 and isinstance(value, (int, float)):
                clean_data[section][slug] = round(float(value) / scale, 2)
            else:
                clean_data[section][slug] = value
        else:
            clean_data["unknown"][f"dp_{dp_id}"] = value
    return clean_data


def update_global_state(status, data=None, error=None):
    with data_lock:
        LATEST_DATA['timestamp'] = time.time()
        LATEST_DATA['status'] = status
        if error:
            LATEST_DATA['error'] = str(error)
        if data:
            LATEST_DATA['data'] = data
            LATEST_DATA['error'] = None


# --- TUYA WORKER THREAD ---
def tuya_worker_loop(config):
    log("Tuya Worker started.")
    raw_dps_cache = {}

    while True:
        try:
            d = tinytuya.OutletDevice(config['device_id'], config['ip_address'], config['local_key'])
            d.set_version(float(config.get('protocol_version', 3.3)))
            d.set_socketPersistent(True)

            log(f"Connecting to {config['ip_address']}...")

            try:
                status_data = d.status()
                if 'dps' in status_data:
                    raw_dps_cache.update(status_data['dps'])
                    clean = process_raw_dps(raw_dps_cache)
                    update_global_state("online", data=clean)
                    log("Initial connection successful. Data received.")
                else:
                    log(f"Initial connection made, but no DPS? {status_data}")
            except Exception as e:
                log(f"Initial status fetch failed: {e}")
                raise e

            last_heartbeat = time.time()

            while True:
                # A. Process any pending write commands first
                while not command_queue.empty():
                    try:
                        cmd = command_queue.get_nowait()
                        dps_to_set = cmd.get('dps', {})
                        if dps_to_set:
                            # tinytuya expects integer keys
                            int_dps = {int(k): v for k, v in dps_to_set.items()}
                            result = d.set_multiple_values(int_dps)
                            if result and 'Error' in result:
                                log(f"Set command error: {result['Error']}")
                            else:
                                log(f"Set command sent: {dps_to_set}")
                    except queue.Empty:
                        break
                    except Exception as e:
                        log(f"Set command failed: {e}. Reconnecting...")
                        raise e

                # B. Check for incoming pushed updates
                if d.socket:
                    r, _, _ = select.select([d.socket], [], [], 0.1)
                    if r:
                        try:
                            payload = d.receive()
                            if payload and 'dps' in payload:
                                raw_dps_cache.update(payload['dps'])
                                clean = process_raw_dps(raw_dps_cache)
                                update_global_state("online", data=clean)
                        except Exception as e:
                            log(f"Read failed: {e}. Reconnecting...")
                            raise e

                # C. Periodic heartbeat / full state resync
                if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                    try:
                        refresh_data = d.status()
                        if 'dps' in refresh_data:
                            raw_dps_cache.update(refresh_data['dps'])
                            clean = process_raw_dps(raw_dps_cache)
                            update_global_state("online", data=clean)
                        elif 'Error' in refresh_data:
                            raise Exception(f"Tuya Error: {refresh_data['Error']}")
                        last_heartbeat = time.time()
                    except Exception as e:
                        log(f"Heartbeat failed: {e}. Reconnecting...")
                        update_global_state("reconnecting", error=e)
                        break

        except Exception as e:
            log(f"Connection failed: {e}. Retrying in 30s...")
            update_global_state("offline", error=e)
            time.sleep(30)


# --- HTTP SERVER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            with data_lock:
                response_data = json.dumps(LATEST_DATA)
            self.wfile.write(response_data.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/set':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "invalid JSON"}')
                return

            dps = payload.get('dps')
            if not isinstance(dps, dict) or not dps:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "missing or empty dps"}')
                return

            with data_lock:
                current_status = LATEST_DATA['status']

            if current_status not in ('online', 'reconnecting'):
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"device {current_status}"}).encode())
                return

            command_queue.put({'dps': dps})
            self.send_response(202)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"queued": true}')
        else:
            self.send_response(404)
            self.end_headers()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


def start_http_server():
    server = ThreadedHTTPServer(('0.0.0.0', HTTP_PORT), SimpleHandler)
    log(f"HTTP API serving on port {HTTP_PORT}")
    server.serve_forever()


# --- MAIN ---
if __name__ == "__main__":
    conf = load_config()

    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    try:
        tuya_worker_loop(conf)
    except KeyboardInterrupt:
        log("Stopping service...")
        sys.exit(0)
