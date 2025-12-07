# chatbot.py
import re
import random
import sys
import sqlite3
from datetime import datetime
from flask import session

from rapidfuzz import fuzz
import sqlite3

def search_faq(user_message):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    cur.execute("SELECT question, answer FROM faqs")
    rows = cur.fetchall()
    conn.close()

    best_score = 0
    best_answer = None

    for q, a in rows:
        score = fuzz.ratio(user_message.lower(), q.lower())
        if score > best_score:
            best_score = score
            best_answer = a

    return best_answer if best_score >= 70 else None

# ---------------------------
# Intent keywords & confidence
# ---------------------------
INTENT_KEYWORDS = {
    "greet": ["hi", "hello", "hey", "hii", "good morning", "good afternoon", "good evening"],
    "thanks": ["thank", "thanks", "thx", "thank you"],
    "goodbye": ["bye", "goodbye", "exit", "quit"],
    "help": ["help", "options", "what can you do"],
    "balance": ["balance", "amount in account", "bank balance"],
    "transaction": ["last transaction", "previous txn", "latest transaction", "transaction history", "recent transaction"],
    "loan_inquiry": ["loan", "apply loan", "loan details", "loan inquiry"],
    "loan_documents": ["documents", "loan documents", "required documents"],
    "card_request": ["new card", "get card", "apply card", "debit card", "credit card"],
    "card_block": ["block card", "block my card", "lost card"],
    "card_unblock": ["unblock card", "activate card"],
    "transfer": ["send money", "transfer money", "send amount", "pay", "transfer to"],
    "open_account": ["open account", "new account", "create account"],
    "feedback": ["feedback", "problem", "issue", "drawback", "not good"],
    "acknowledge": ["ok", "okay", "fine", "alright"],
    "fallback": []
}

def compute_confidence(user_text: str, intent: str) -> float:
    """Compute a rule-based confidence for a detected intent."""
    text = (user_text or "").lower()
    if intent not in INTENT_KEYWORDS:
        return 0.95
    keywords = INTENT_KEYWORDS[intent]
    if not keywords:
        return 0.97

    matches = 0
    for kw in keywords:
        if kw in text:
            matches += 1

    ratio = matches / len(keywords)
    if ratio == 0:
        return 0.98
    if ratio < 0.5:
        return 0.79
    return round(min(1.0, 0.80 + ratio * 0.20), 2)

# ---------------------------
# pack helper to standardize returns
# ---------------------------
def pack(response: str, intent: str, user_text: str, extra=None):
    """
    Short helper to return unified tuples.
    - Normal: (response, intent, confidence)
    - With extra (e.g., new_balance): (response, extra, intent, confidence)
    """
    confidence = compute_confidence(user_text, intent)
    if extra is None:
        return response, intent, confidence
    else:
        return response, extra, intent, confidence

# ---------------------------
# DB helpers (same as before)
# ---------------------------
def get_db_balance(acc):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    cur.execute("SELECT currentBalance FROM users WHERE accountNumber=?", (acc,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_last_transaction(acc):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            CASE 
                WHEN sender_acc = ? THEN receiver_name
                ELSE (SELECT accountName FROM users WHERE accountNumber = sender_acc)
            END AS party_name,
            amount,
            txn_type,
            txn_date,
            txn_time
        FROM transactions
        WHERE sender_acc = ? OR receiver_acc = ?
        ORDER BY id DESC
        LIMIT 1
    """, (acc, acc, acc))

    row = cur.fetchone()
    conn.close()
    return row

# ---------------------------
# Static data
# ---------------------------
DEBIT_CARDS = ["123456789876", "123569044596"]
CREDIT_CARDS = ["850634784875", "908685755967"]
BLOCKED_CARDS = set()

# ---------- Session memory ----------
memory = {
    "account_number": None,
    "card_number": None,
    "card_type": None,
    "mobile": None,
    "aadhar": None,
    "last_domain": None,
    "need_reason": True,
    "card_block_reason": None,
    "loan_type": None,
    "transfer_amount": None,
    "transfer_name": None,
    "transfer_target_acc": None,
    "open_account_type": None,
}

# ---------- Extractors ----------
def extract_account(text):
    m = re.search(r"\b[A-Z0-9]{10}\b", (text or "").upper())
    return m.group(0) if m else None

def extract_card(text):
    m = re.search(r"\b\d{12}\b", (text or ""))
    return m.group(0) if m else None

def extract_mobile(text):
    m = re.search(r"\b[6-9]\d{9}\b", (text or ""))
    return m.group(0) if m else None

def extract_aadhar(text):
    s = re.sub(r"\D", "", (text or ""))
    m = re.search(r"\b\d{12}\b", s)
    return m.group(0) if m else None

def extract_income(text):
    m = re.search(r"\b(?:rs\.?\s*)?(\d{3,9})\b", (text or "").replace(",", ""))
    return int(m.group(1)) if m else None

# ---------- Helpers ----------
def clear_domain(domain):
    if domain in ("balance", "transaction"):
        memory["account_number"] = None
        memory["last_domain"] = None
    elif domain == "card":
        memory["card_number"] = None
        memory["card_type"] = None
        memory["mobile"] = None
        memory["aadhar"] = None
        memory["last_domain"] = None
        memory["need_reason"] = True
        memory["card_block_reason"] = None
    elif domain == "card_block":
        memory["card_number"] = None
        memory["last_domain"] = None
        memory["need_reason"] = True
        memory["card_block_reason"] = None
    elif domain == "open_account":
        memory["mobile"] = None
        memory["aadhar"] = None
        memory["last_domain"] = None
    elif domain == "loan":
        memory["loan_type"] = None
        memory["last_domain"] = None
    elif domain == "transfer":
        memory["transfer_amount"] = None
        memory["transfer_name"] = None
        memory["transfer_target_acc"] = None

def intent_label(label):
    return f" ({label})"

# ---------- Bot logic ----------
def bot(user_input, sender_account=None):

    faq_answer = search_faq(user_input)
    if faq_answer:
        return faq_answer, "faq_answered", 0.95
    
    """
    Main bot function.
    Returns:
      - (message, intent, confidence)
      - or for transfer success: (message, new_balance, intent, confidence)
    """
    if user_input is None:
        user_input = ""

    text = user_input.strip()
    low = text.lower()

    acc = extract_account(text)
    card = extract_card(text)
    mob = extract_mobile(text)
    aad = extract_aadhar(text)
    inc = extract_income(text)

    if acc:
        memory["account_number"] = acc
    if card:
        memory["card_number"] = card
    if mob:
        memory["mobile"] = mob
    if aad:
        memory["aadhar"] = aad

    # HELP
    if low in ["help", "what can you do", "options"]:
        response = (
            "I can help with:\n"
            "- Check balance\n"
            "- Last transaction\n"
            "- New debit/credit card\n"
            "- Block/unblock card\n"
            "- Loan eligibility\n"
            "- Open new account\n"
            "Just tell me what you need!"
        )
        return pack(response, "help", user_input)

    # GREET
    greet_words = ["hi", "hello", "hey", "hii", "good morning", "good afternoon", "good evening"]
    if any(low == g for g in greet_words):
        greetings = [
            "Hello! How can I assist you today?",
            "Hi there! What can I do for you?",
            "Hey! How may I help you today?",
            "Good day! How can I support you?",
            "Welcome! How can I make your banking easier?",
        ]
        return pack(random.choice(greetings), "greet", user_input)

    # THANKS
    if any(w in low for w in ["thank", "thanks", "thank you", "thx"]):
        replies = [
            "You're welcome!",
            "Glad I could help!",
            "Anytime — happy to assist.",
            "No problem — always here to help.",
            "My pleasure!",
        ]
        return pack(random.choice(replies), "thanks", user_input)

    # GOODBYE
    if any(w in low for w in ["bye", "byee", "byeee", "exit", "quit", "goodbye"]):
        return pack("Goodbye! Have a great day.", "goodbye", user_input)

    # OUT OF SCOPE
    oos = ["movie", "movies", "recipe", "python", "weather", "news", "sports"]
    if any(w in low.split() for w in oos):
        return pack("I'm sorry — I can answer only banking-related questions.", "fallback", user_input)

    # CHECK BALANCE
    if "balance" in low:
        if not sender_account:
            return pack("Unable to verify your account. Please log in again.", "fallback", user_input)
        bal = get_db_balance(sender_account)
        if bal is None:
            return pack("Account not found.", "fallback", user_input)
        return pack(f"Your current balance is ₹{bal}.", "balance", user_input)

    # TRANSACTION HISTORY
    txn_phrases = [
        "last transaction", "last txn", "previous transaction", "previous txn",
        "latest transaction", "recent transaction", "transaction history",
        "last transaction details", "previous transaction details", "latest txn",
        "recent txn",
    ]
    if any(p in low for p in txn_phrases):
        if not sender_account:
            return pack("Unable to verify your account. Please log in again.", "fallback", user_input)
        txn = get_last_transaction(sender_account)
        if not txn:
            return pack("You have no previous transactions.", "transaction", user_input)
        receiver_name, amount, txn_type, date, time = txn
        if txn_type == "debit":
            msg = f"Your last transaction: Sent ₹{amount} to {receiver_name} on {date} at {time}."
            return pack(msg, "transaction", user_input)
        else:
            sender_name = receiver_name
            msg = f"Your last transaction: Received ₹{amount} from {sender_name} on {date} at {time}."
            return pack(msg, "transaction", user_input)

    # NEW CARD REQUEST
    if any(w in low for w in ["new card", "get card", "i want a card", "apply card", "want a card"]) \
            or "credit card" in low or "debit card" in low:
        memory["last_domain"] = "card"
        if "credit" in low:
            memory["card_type"] = "credit"
        elif "debit" in low:
            memory["card_type"] = "debit"
        else:
            return pack("Would you like a debit card or a credit card?", "card_request", user_input)

        return pack("Please provide your 10-digit mobile number and 12-digit Aadhaar number.", "card_request", user_input)

    if memory.get("last_domain") == "card" and memory.get("card_type"):
        mobile = extract_mobile(text)
        aadhar = extract_aadhar(text)
        if mobile:
            memory["mobile"] = mobile
        if aadhar:
            memory["aadhar"] = aadhar
        if memory.get("mobile") and memory.get("aadhar"):
            if memory["card_type"] == "debit":
                cardnum = random.choice(DEBIT_CARDS)
                clear_domain("card")
                return pack(f"Your debit card request is approved! Card number: {cardnum}.", "card_request", user_input)
            elif memory["card_type"] == "credit":
                cardnum = random.choice(CREDIT_CARDS)
                clear_domain("card")
                return pack(f"Your credit card request is approved! Card number: {cardnum}.", "card_request", user_input)
        if memory.get("mobile") and not memory.get("aadhar"):
            return pack("Mobile number received. Now provide your 12-digit Aadhaar number.", "card_request", user_input)
        if memory.get("aadhar") and not memory.get("mobile"):
            return pack("Aadhaar received. Now provide your 10-digit mobile number.", "card_request", user_input)
        return pack("Please provide your 10-digit mobile and 12-digit Aadhaar numbers.", "card_request", user_input)

    # BLOCK CARD
    if re.search(r"\bblock\b", low) and not re.search(r"\bunblock\b", low):
        memory["last_domain"] = "block_card"
        card = extract_card(text)
        if card:
            if card in BLOCKED_CARDS:
                memory["last_domain"] = None
                return pack(f"Card {card} is already blocked.", "card_block", user_input)
            BLOCKED_CARDS.add(card)
            memory["last_domain"] = None
            return pack(f"Card {card} has been blocked successfully.", "card_block", user_input)
        return pack("Please provide your 12-digit card number to block the card.", "card_block", user_input)

    if memory.get("last_domain") == "block_card":
        card = extract_card(text)
        if card:
            if card in BLOCKED_CARDS:
                memory["last_domain"] = None
                return pack(f"Card {card} is already blocked.", "card_block", user_input)
            BLOCKED_CARDS.add(card)
            memory["last_domain"] = None
            return pack(f"Card {card} has been blocked successfully.", "card_block", user_input)
        return pack("Please provide a valid 12-digit card number.", "card_block", user_input)

    # UNBLOCK CARD
    if re.search(r"\bunblock\b", low) or re.search(r"\bactivate\b", low) or "unblockcard" in low.replace(" ", ""):
        memory["last_domain"] = "unblock_card"
        card = extract_card(text)
        if card:
            if card not in BLOCKED_CARDS:
                memory["last_domain"] = None
                return pack(f"Card {card} is already active (not blocked).", "card_unblock", user_input)
            BLOCKED_CARDS.remove(card)
            memory["last_domain"] = None
            return pack(f"Card {card} has been unblocked successfully.", "card_unblock", user_input)
        return pack("Please provide your 12-digit card number to unblock the card.", "card_unblock", user_input)

    if memory.get("last_domain") == "unblock_card":
        card = extract_card(text)
        if card:
            if card not in BLOCKED_CARDS:
                memory["last_domain"] = None
                return pack(f"Card {card} is already active (not blocked).", "card_unblock", user_input)
            BLOCKED_CARDS.remove(card)
            memory["last_domain"] = None
            return pack(f"Card {card} has been unblocked successfully.", "card_unblock", user_input)
        return pack("Please provide a valid 12-digit card number.", "card_unblock", user_input)

    # MONEY TRANSFER — MAIN TRIGGER
    if any(w in low for w in ["send money", "transfer money", "send amount", "pay", "send money to", "transfer to"]):
        memory["last_domain"] = "transfer"
        inline_acc = extract_account(text)
        if inline_acc:
            memory["transfer_target_acc"] = inline_acc
        if not memory.get("transfer_target_acc"):
            return pack("Please enter the receiver's 10-digit account number.", "transfer", user_input)
        if not memory.get("transfer_name"):
            return pack("Please confirm the receiver's name.", "transfer", user_input)
        if not memory.get("transfer_amount"):
            amt = extract_income(text)
            if amt:
                memory["transfer_amount"] = amt
            else:
                return pack("How much amount do you want to send?", "transfer", user_input)
        if not sender_account:
            return pack("Unable to verify your account. Please log in again.", "fallback", user_input)
        memory["last_domain"] = "transfer"

    # CONTINUE TRANSFER STEP-BY-STEP
    if memory.get("last_domain") == "transfer":
        # 1) Ask receiver account number
        if not memory.get("transfer_target_acc"):
            acc = extract_account(text)
            if acc:
                memory["transfer_target_acc"] = acc
                return pack("Please confirm the receiver's name.", "transfer", user_input)
            return pack("Enter a valid 10-digit receiver account number.", "transfer", user_input)

        # 2) Ask receiver name
        if not memory.get("transfer_name"):
            candidate = text.strip()
            invalid_words = {"ok", "okay", "k", "okk", "fine", "hmm", "yes", "no", "send", "amount", "money", "transfer", "pay"}
            if (
                candidate.lower() not in invalid_words
                and candidate
                and all(part.isalpha() for part in candidate.split())
            ):
                memory["transfer_name"] = candidate.title()
                return pack("How much amount do you want to send?", "transfer", user_input)
            return pack("Please enter the receiver's name.", "transfer", user_input)

        # 3) Ask amount → complete transfer
        if not memory.get("transfer_amount"):
            amt = extract_income(text)
            if not amt:
                return pack("Enter a valid amount.", "transfer", user_input)
            memory["transfer_amount"] = amt

            # Now complete transfer
            sender = sender_account
            recv_acc = memory["transfer_target_acc"]
            recv_name = memory["transfer_name"]
            amt_val = memory["transfer_amount"]

            # STEP 1: FETCH BALANCE
            sender_balance = get_db_balance(sender)
            if sender_balance is None:
                clear_domain("transfer")
                return pack("Unable to fetch your balance. Please login again.", "fallback", user_input)

            # STEP 2: CHECK BALANCE
            if sender_balance < amt_val:
                clear_domain("transfer")
                return pack("You do not have enough balance to complete this transfer.", "transfer", user_input)

            # STEP 3: UPDATE BALANCE IN SQLITE
            new_balance = sender_balance - amt_val
            conn = sqlite3.connect("bank.db")
            cur = conn.cursor()
            cur.execute("""
                UPDATE users
                SET currentBalance = ?
                WHERE accountNumber = ?
            """, (new_balance, sender))
            conn.commit()
            conn.close()
            session["user_balance"] = new_balance

            # STEP 4: INSERT TRANSACTION RECORD
            txn_id = "TXN" + str(random.randint(100000, 999999))
            now = datetime.now()
            date = now.strftime("%Y-%m-%d")
            time = now.strftime("%H:%M")
            conn = sqlite3.connect("bank.db")
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO transactions (
                    sender_acc, receiver_acc, receiver_name,
                    amount, txn_type, txn_date, txn_time, txn_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sender, recv_acc, recv_name,
                amt_val, "debit", date, time, txn_id
            ))
            conn.commit()
            conn.close()

            # STEP 4B: UPDATE RECEIVER BALANCE
            receiver_balance = get_db_balance(recv_acc)
            if receiver_balance is not None:
                new_receiver_balance = receiver_balance + amt_val
                conn = sqlite3.connect("bank.db")
                cur = conn.cursor()
                cur.execute("""
                    UPDATE users
                    SET currentBalance = ?
                    WHERE accountNumber = ?
                """, (new_receiver_balance, recv_acc))
                conn.commit()
                conn.close()

            # STEP 5: UPDATE LAST TRANSACTION IN USER TABLE
            conn = sqlite3.connect("bank.db")
            cur = conn.cursor()
            cur.execute("""
                UPDATE users
                SET prevTxn=?, txnType='debit', lastTxnDate=?, lastTxnTime=?, receiverName=?, receiverAcc=?
                WHERE accountNumber=?
            """, (amt_val, date, time, recv_name, recv_acc, sender))
            conn.commit()
            conn.close()

            # Reset transfer memory
            memory["transfer_amount"] = None
            memory["transfer_name"] = None
            memory["transfer_target_acc"] = None
            memory["last_domain"] = None

            msg = f"₹{amt_val} has been successfully sent to {recv_name} (Account: {recv_acc}). Transaction ID: {txn_id}"
            return pack(msg, "transfer_success", user_input, new_balance)

    # LOAN DOCUMENTS
    loan_doc_phrases = [
        "documents required", "required documents", "loan documents",
        "what are the documents", "documents needed", "loan requirement",
        "requirements for loan",
    ]
    if any(p in low for p in loan_doc_phrases):
        response = (
            "Documents required for any loan:\n"
            "• Aadhaar Card\n"
            "• PAN Card\n"
            "• 6 months bank statement\n"
            "• Salary slips / income proof\n"
            "• Address proof\n"
            "• Passport-size photo\n"
            "Note: Please visit the nearest branch or call customer care for more details."
        )
        return pack(response, "loan_documents", user_input)

    # LOAN INQUIRY
    if "loan" in low and memory.get("last_domain") != "loan":
        memory["last_domain"] = "loan"
        return pack("Available loans: Home, Personal, Car, Education, Business. Which loan would you like?", "loan_inquiry", user_input)

    if memory.get("last_domain") == "loan" and not memory.get("loan_type"):
        for k in ["home", "personal", "car", "education", "business"]:
            if k in low:
                memory["loan_type"] = k
                return pack(f"You chose {k.title()} Loan. Please enter your monthly income (numbers only).", "loan_ask_income", user_input)
        return pack("Please choose one: Home, Personal, Car, Education, or Business.", "loan_inquiry", user_input)

    if memory.get("last_domain") == "loan" and memory.get("loan_type") and inc is not None:
        thresholds = {
            "home": 40000,
            "personal": 20000,
            "car": 25000,
            "education": 15000,
            "business": 30000,
        }
        lt = memory.get("loan_type")
        min_inc = thresholds.get(lt, 20000)
        if inc >= min_inc:
            clear_domain("loan")
            return pack(f"You are eligible for the {lt.title()} Loan (min monthly income required ₹{min_inc}).", "loan_approve", user_input)
        else:
            clear_domain("loan")
            return pack(f"Sorry, you are not eligible for the {lt.title()} Loan. Minimum required monthly income is ₹{min_inc}.", "loan_reject", user_input)

    # OPEN ACCOUNT
    if any(w in low for w in ["open account", "new account", "create account"]):
        memory["last_domain"] = "open_account"
        return pack("Which type: Savings, Current, or Mutual?", "open_account", user_input)

    if memory.get("last_domain") == "open_account" and any(w in low for w in ["savings", "current", "mutual"]):
        memory["open_account_type"] = ("savings" if "savings" in low else ("current" if "current" in low else "mutual"))
        return pack("Eligibility: Aadhaar, PAN (if required), Mobile number. Please provide mobile then Aadhaar.", "account_eligibility", user_input)

    if memory.get("last_domain") == "open_account" and memory.get("mobile") and memory.get("aadhar"):
        new_acc = "ACNT" + str(random.randint(10000000, 99999999))
        clear_domain("open_account")
        return pack(f"Your new account is created! Account number: {new_acc}.", "provide_new_account", user_input)

    # FEEDBACK
    if any(w in low for w in ["drawback", "feedback", "problem", "issue", "not good"]):
        return pack("Thanks for the feedback — I'll try to improve.", "feedback", user_input)

    # OK / Affirmation
    if low in ["ok", "okay", "k", "okk", "okayy", "fine", "alright", "hmm"]:
        return pack("Alright! How can I help you further?", "acknowledge", user_input)

    # FALLBACK
    return pack("Sorry, I didn’t understand that. Could you rephrase?", "fallback", user_input)


# ---------- Terminal Loop ----------
def run_terminal():
    print("\n🟢 Bank Assistant: Hello! How can I assist you today?")

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n🟢 Bank Assistant: Goodbye! Have a great day.")
            sys.exit(0)

        if not user:
            continue

        if user.lower() in ("bye", "byee", "byeee", "exit", "quit", "goodbye"):
            print("🟢 Bank Assistant: Goodbye! Have a great day. (goodbye)")
            break

        reply = bot(user)
        # reply may be (resp, intent, conf) or (resp, extra, intent, conf)
        if isinstance(reply, tuple):
            if len(reply) == 3:
                resp, intent, conf = reply
                print(f"🟢 Bank Assistant: {resp} ({intent}) [conf={conf}]")
            elif len(reply) == 4:
                resp, extra, intent, conf = reply
                # extra might be new_balance — print it nicely
                print(f"🟢 Bank Assistant: {resp} | extra={extra} ({intent}) [conf={conf}]")
            else:
                print("🟢 Bank Assistant:", reply)
        else:
            print("🟢 Bank Assistant:", reply)


if __name__ == "__main__":
    run_terminal()
