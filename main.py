
import os
import time
from keep_alive import keep_alive

def main():
    # Install dependencies once
    os.system("pip install -r requirements.txt")
    
    keep_alive()
    
    while True:
        try:
            os.system("python3 bot_verifikasi_roomnakal_static.py")
        except Exception as e:
            print("❌ Bot error, restart dalam 5 detik...")
            print(f"Error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    main()
