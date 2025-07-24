import asyncio
import logging
import json
import sys
import signal
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD

# Enable detailed logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class GracefulKiller:
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"\n🛑 Signal {signum} received, shutting down gracefully...")
        self.kill_now = True

async def connect_with_retry(conn, max_retries=3, delay=5):
    """연결을 여러 번 시도하는 함수"""
    for attempt in range(max_retries):
        try:
            print(f"🔄 Connection attempt {attempt + 1}/{max_retries}")
            await conn.connect()
            print("✅ Connection successful!")
            return True
        except Exception as e:
            print(f"❌ Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"⏳ Waiting {delay} seconds before retry...")
                await asyncio.sleep(delay)
            else:
                print("🚫 All connection attempts failed")
                return False
    return False

async def main():
    killer = GracefulKiller()
    conn = None
    
    try:
        print("🚀 Starting GO2 SportMode connection...")
        
        # Choose a connection method (uncomment the correct one)
        # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip="192.168.8.181")
        # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, serialNumber="B42D2000XXXXXXXX")
        conn = Go2WebRTCConnection(WebRTCConnectionMethod.Remote, serialNumber="B42D4000O358LD01", username="mrt2020@daum.net", password="dodan1004~")
        # conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

        # Connect to the WebRTC service with retry logic
        if not await connect_with_retry(conn):
            print("🚫 Failed to establish connection after retries")
            return

        print("📡 Connection established, waiting for data channel...")
        await conn.datachannel.wait_datachannel_open(timeout=30)

        if killer.kill_now:
            return

        ####### NORMAL MODE ########
        print("🔍 Checking current motion mode...")

        # Get the current motion_switcher status
        response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {"api_id": 1001}
        )

        if response['data']['header']['status']['code'] == 0:
            data = json.loads(response['data']['data'])
            current_motion_switcher_mode = data['name']
            print(f"📋 Current motion mode: {current_motion_switcher_mode}")

        # Switch to "normal" mode if not already
        if current_motion_switcher_mode != "normal":
            print(f"🔄 Switching motion mode from {current_motion_switcher_mode} to 'normal'...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], 
                {
                    "api_id": 1002,
                    "parameter": {"name": "normal"}
                }
            )
            await asyncio.sleep(5)  # Wait while it stands up

        if killer.kill_now:
            return

        # Perform a "Hello" movement
        print("👋 Performing 'Hello' movement...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {"api_id": SPORT_CMD["Hello"]}
        )

        await asyncio.sleep(1)

        # Perform a "Move Forward" movement
        print("⬆️ Moving forward...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["Move"],
                "parameter": {"x": 0.5, "y": 0, "z": 0}
            }
        )

        await asyncio.sleep(3)

        if killer.kill_now:
            return

        # Perform a "Move Backward" movement
        print("⬇️ Moving backward...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["Move"],
                "parameter": {"x": -0.5, "y": 0, "z": 0}
            }
        )

        await asyncio.sleep(3)

        if killer.kill_now:
            return

        ####### AI MODE ########

        # Switch to AI mode
        print("🤖 Switching motion mode to 'AI'...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"], 
            {
                "api_id": 1002,
                "parameter": {"name": "ai"}
            }
        )
        await asyncio.sleep(10)

        if killer.kill_now:
            return

        # Switch to Handstand Mode
        print("🤸 Switching to Handstand Mode...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["StandOut"],
                "parameter": {"data": True}
            }
        )

        await asyncio.sleep(5)

        # Switch back to StandUp Mode
        print("🧍 Switching back to StandUp Mode...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], 
            {
                "api_id": SPORT_CMD["StandOut"],
                "parameter": {"data": False}
            }
        )

        # Keep the program running for a while
        print("⏰ Program will run for 10 minutes. Press Ctrl+C to exit early.")
        for i in range(600):  # 10 minutes instead of 1 hour
            if killer.kill_now:
                break
            await asyncio.sleep(1)
    
    except asyncio.TimeoutError as e:
        print(f"⏰ Timeout error: {e}")
        logging.error(f"Timeout error: {e}")
    except ConnectionError as e:
        print(f"🔌 Connection error: {e}")
        logging.error(f"Connection error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logging.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        # Clean up connection
        if conn:
            try:
                print("🧹 Cleaning up connection...")
                # Add any cleanup code here if available
                await asyncio.sleep(1)
            except Exception as e:
                print(f"⚠️ Error during cleanup: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logging.error(f"Fatal error: {e}", exc_info=True)
    finally:
        print("👋 Program terminated")
        sys.exit(0) 