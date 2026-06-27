import time
import requests



class DweetClient:

    def __init__(self, channel="omnisync-fallback-channel-v3", my_role="laptop", target_role="android"):
        """Setting up the exact URLs to avoid relying on global variables"""
        
        self.server = "https://dweet.cc"
        self.channel = channel
        self.my_role = my_role
        self.target_role = target_role

        self.broadcast_url = f"{self.server}/dweet/for/{self.channel}-{self.my_role}"
        self.listen_url = f"{self.server}/get/latest/dweet/for/{self.channel}-{self.target_role}"

    def broadcast_presence(self, local_ip, public_key_base64):
        """
        Drops the payload on Dweet.cc compiled with the timestamp to avoid android from accidentally taking up old cached payloads.
        """
        # url = f"{SIGNALING_SERVER}/dweet/for/{SYNC_CHANNEL}-{MY_ROLE}"

        print(f"[DEBUG] Dweet broadcast URL: {self.broadcast_url}")

        print("Broadcasting presence to Dweet.cc through JSON POST")

        try:
            payload = {
                "ip": local_ip,
                "public_key": public_key_base64,
                "timestamp": int(time.time())
            }

            response = requests.post(self.broadcast_url, data=payload, timeout=3)


            print(f"[DEBUG] Response URL: {response.request.url}")
            print(f"[DEBUG] Response Body: {response.request.body}")
            print(f"[DEBUG] Response Headers: {response.request.headers}")


            # print(f"[DEBUG] Dweet Status Code: {response.status_code}")
            # print(f"[DEBUG] Dweet Server Replied {response.text}")

            if response.status_code == 200:
                print("Broadcast Successful!")
                print(f"Dweet Server Replied: {response.text}")
            else:
                print(f"[WARNING] Dweet server rejected the broadcast. Code: {response.status_code}")
                print(f"Dweet Server Replied: {response.text}")

            print("[DEBUG] INITIAL JSON Payload Successfully sent over Dweet for android device to read.")

        except Exception as e:
            print(f"Broadcast Failed: {e}")


    def listen_for_target(self):
        """
        Polls Dweet.cc in a infinite loop.
        Only returns when it finds a fresh key sent in by android containing timestamp as well.
        """

        print(f"Listening for {self.target_role}...")

        while True:
            try:
                response = requests.get(self.listen_url, timeout=10)
                # Pings the url we have and then check that if the response given is OK i.e. a 200 status code
                #  this means the android phone has broadcasted then and if not then it might return a 404 Not Found error

                print(f"[DEBUG] Response URL: {response.request.url}")
                print(f"[DEBUG] Response Text: {response.text}")



                if response.status_code == 200:
                    data = response.json()
                    if "with" in data and len(data["with"]) > 0:
                        content = data["with"][0]["content"]
                        # If the android successfully broadcast, then the server sends the data as a giant block of text, the code i.e. 'response.json()' converts that text into a python dictionary
                        # further on we use slicing to look for the 'with' keyword and then in that we look for the 'content' keyword since dweet wraps data in layers.

                        if "ip" in content and "public_key" in content and "timestamp" in content:
                            target_timestamp = int(content.get("timestamp"))
                            current_time = int(time.time())

                            age_in_seconds = current_time - target_timestamp

                            if age_in_seconds > 60:
                                print(f"Found a old Android key i.e. {age_in_seconds}s old. Waiting for a fresh key...")
                                time.sleep(3)
                                continue

                        """[DEBUGGING CODE]"""

                        target_ip = content.get("ip")
                        target_pub_key = content.get("public_key")

                        if target_ip and target_pub_key:
                            print(f"\n[DEBUG] Recorded Android IP: {target_ip}")
                            print(f"\n[DEBUG] Recorded Android Public Key: {target_pub_key}")


                        print(f"Found the {self.target_role} with IP: {content['ip']}")
                        return target_ip, target_pub_key
                    # The moment the script finds the data, the return statement kills the infinite while True loop and passes the android's IP
                    # and public key that is given in the data to the main script so it can start deriving shared key
                    
            except Exception as e:
                print(f"[ERROR] Loop crashed because: {e}")
                pass
            time.sleep(3)