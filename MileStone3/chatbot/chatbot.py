# chatbot.py
import re
import random
import sys
import sqlite3
from datetime import datetime
from flask import session

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
}

# ---------- Extractors ----------
def extract_account(text):
    m = re.search(r"\b[A-Z0-9]{10}\b", text.upper())
    return m.group(0) if m else None


def extract_card(text):
    m = re.search(r"\b\d{12}\b", text)
    return m.group(0) if m else None


def extract_mobile(text):
    m = re.search(r"\b[6-9]\d{9}\b", text)
    return m.group(0) if m else None


def extract_aadhar(text):
    s = re.sub(r"\D", "", text)
    m = re.search(r"\b\d{12}\b", s)
    return m.group(0) if m else None


def extract_income(text):
    m = re.search(r"\b(?:rs\.?\s*)?(\d{3,9})\b", text.replace(",", ""))
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
        return (
            "I can help with:\n"
            "- Check balance\n"
            "- Last transaction\n"
            "- New debit/credit card\n"
            "- Block/unblock card\n"
            "- Loan eligibility\n"
            "- Open new account\n"
            "Just tell me what you need!"
        ) + intent_label("help")

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
        return random.choice(greetings) + intent_label("greet")

    # THANKS
    if any(w in low for w in ["thank", "thanks", "thank you", "thx"]):
        replies = [
            "You're welcome!",
            "Glad I could help!",
            "Anytime — happy to assist.",
            "No problem — always here to help.",
            "My pleasure!",
        ]
        return random.choice(replies) + intent_label("thanks")

    # GOODBYE
    if any(w in low for w in ["bye", "byee", "byeee", "exit", "quit", "goodbye"]):
        return "Goodbye! Have a great day." + intent_label("goodbye")

    # OUT OF SCOPE
    oos = ["movie", "movies", "recipe", "python", "weather", "news", "sports"]
    if any(w in low.split() for w in oos):
        return "I'm sorry — I can answer only banking-related questions." + intent_label("out_of_scope")

    # ✅ CHECK BALANCE FROM SQLITE
    if "balance" in low:
        if not sender_account:
            return "Unable to verify your account. Please log in again."

        bal = get_db_balance(sender_account)
        if bal is None:
            return "Account not found."

        return f"Your current balance is ₹{bal}."
    
    # TRANSACTION HISTORY
    txn_phrases = [
        "last transaction", "last txn", "previous transaction", "previous txn",
        "latest transaction", "recent transaction", "transaction history",
        "last transaction details", "previous transaction details", "latest txn",
        "recent txn",
    ]

    # ============================
    # 🔵 LAST TRANSACTION FROM SQLITE
    # ============================
    if any(p in low for p in txn_phrases):
        if not sender_account:
            return "Unable to verify your account. Please log in again."

        txn = get_last_transaction(sender_account)

        if not txn:
            return "You have no previous transactions."

        receiver_name, amount, txn_type, date, time = txn

        if txn_type == "debit":
            # You SENT money → receiver_name is correct
            return f"Your last transaction: Sent ₹{amount} to {receiver_name} on {date} at {time}."
        else:
            # You RECEIVED money → receiver_name actually contains SENDER NAME in your DB
            sender_name = receiver_name  
            return f"Your last transaction: Received ₹{amount} from {sender_name} on {date} at {time}."


    # NEW CARD REQUEST
    if any(w in low for w in ["new card", "get card", "i want a card", "apply card", "want a card"]) \
            or "credit card" in low or "debit card" in low:

        memory["last_domain"] = "card"

        if "credit" in low:
            memory["card_type"] = "credit"
        elif "debit" in low:
            memory["card_type"] = "debit"
        else:
            return "Would you like a debit card or a credit card?"

        return "Please provide your 10-digit mobile number and 12-digit Aadhaar number."

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
                return f"Your debit card request is approved! Card number: {cardnum}."

            elif memory["card_type"] == "credit":
                cardnum = random.choice(CREDIT_CARDS)
                clear_domain("card")
                return f"Your credit card request is approved! Card number: {cardnum}."

        if memory.get("mobile") and not memory.get("aadhar"):
            return "Mobile number received. Now provide your 12-digit Aadhaar number."

        if memory.get("aadhar") and not memory.get("mobile"):
            return "Aadhaar received. Now provide your 10-digit mobile number."

        return "Please provide your 10-digit mobile and 12-digit Aadhaar numbers."

    # BLOCK CARD
    if re.search(r"\bblock\b", low) and not re.search(r"\bunblock\b", low):
        memory["last_domain"] = "block_card"
        card = extract_card(text)

        if card:
            if card in BLOCKED_CARDS:
                memory["last_domain"] = None
                return f"Card {card} is already blocked." + intent_label("card_already_blocked")

            BLOCKED_CARDS.add(card)
            memory["last_domain"] = None
            return f"Card {card} has been blocked successfully." + intent_label("block_card_success")

        return "Please provide your 12-digit card number to block the card." + intent_label("ask_block_card_number")

    if memory.get("last_domain") == "block_card":
        card = extract_card(text)
        if card:
            if card in BLOCKED_CARDS:
                memory["last_domain"] = None
                return f"Card {card} is already blocked." + intent_label("card_already_blocked")
            BLOCKED_CARDS.add(card)
            memory["last_domain"] = None
            return f"Card {card} has been blocked successfully." + intent_label("block_card_success")

        return "Please provide a valid 12-digit card number." + intent_label("ask_block_card_number")

    # UNBLOCK CARD
    if re.search(r"\bunblock\b", low) or re.search(r"\bactivate\b", low) or "unblockcard" in low.replace(" ", ""):
        memory["last_domain"] = "unblock_card"
        card = extract_card(text)

        if card:
            if card not in BLOCKED_CARDS:
                memory["last_domain"] = None
                return f"Card {card} is already active (not blocked)." + intent_label("card_not_blocked")

            BLOCKED_CARDS.remove(card)
            memory["last_domain"] = None
            return f"Card {card} has been unblocked successfully." + intent_label("unblock_card_success")

        return "Please provide your 12-digit card number to unblock the card." + intent_label("ask_unblock_card")

    if memory.get("last_domain") == "unblock_card":
        card = extract_card(text)
        if card:
            if card not in BLOCKED_CARDS:
                memory["last_domain"] = None
                return f"Card {card} is already active (not blocked)." + intent_label("card_not_blocked")

            BLOCKED_CARDS.remove(card)
            memory["last_domain"] = None
            return f"Card {card} has been unblocked successfully." + intent_label("unblock_card_success")

        return "Please provide a valid 12-digit card number." + intent_label("ask_unblock_card")

    # ============================
    # 🔵 MONEY TRANSFER — MAIN TRIGGER
    # ============================
    if any(w in low for w in ["send money", "transfer money", "send amount", "pay", "send money to", "transfer to"]):
        memory["last_domain"] = "transfer"

        inline_acc = extract_account(text)
        if inline_acc:
            memory["transfer_target_acc"] = inline_acc

        if not memory.get("transfer_target_acc"):
            return "Please enter the receiver's 10-digit account number." + intent_label("ask_account")

        if not memory.get("transfer_name"):
            return "Please confirm the receiver's name." + intent_label("ask_name")

        if not memory.get("transfer_amount"):
            amt = extract_income(text)
            if amt:
                memory["transfer_amount"] = amt
            else:
                return "How much amount do you want to send?" + intent_label("ask_amount")

        if not sender_account:
            return "Unable to verify your account. Please log in again." + intent_label("fallback")

        # ALL DETAILS PRESENT → complete transfer
        memory["last_domain"] = "transfer"

    # ============================
    # 🔵 CONTINUE TRANSFER STEP-BY-STEP
    # ============================
    if memory.get("last_domain") == "transfer":

        # 1) Ask receiver account number
        if not memory.get("transfer_target_acc"):
            acc = extract_account(text)
            if acc:
                memory["transfer_target_acc"] = acc
                return "Please confirm the receiver's name." + intent_label("ask_name")
            return "Enter a valid 10-digit receiver account number." + intent_label("ask_account")

        # 2) Ask receiver name
        if not memory.get("transfer_name"):
            candidate = text.strip()
            invalid_words = {"ok", "okay", "k", "okk", "fine", "hmm", "yes", "no", "send","amount","money", "transfer","pay"}

            if (
                candidate.lower() not in invalid_words
                and candidate
                and all(part.isalpha() for part in candidate.split())
            ):
                memory["transfer_name"] = candidate.title()
                return "How much amount do you want to send?" + intent_label("ask_amount")

            return "Please enter the receiver's name." + intent_label("ask_name")

        # 3) Ask amount → complete transfer
        if not memory.get("transfer_amount"):
            amt = extract_income(text)
            if not amt:
                return "Enter a valid amount." + intent_label("ask_amount")

            memory["transfer_amount"] = amt

            # Now complete transfer
            sender = sender_account
            recv_acc = memory["transfer_target_acc"]
            recv_name = memory["transfer_name"]
            amt_val = memory["transfer_amount"]

            # --------------- STEP 1: FETCH BALANCE FROM SQLITE ----------------
            sender_balance = get_db_balance(sender)

            if sender_balance is None:
                clear_domain("transfer")
                return "Unable to fetch your balance. Please login again."

            # --------------- STEP 2: CHECK BALANCE ----------------
            if sender_balance < amt_val:
                clear_domain("transfer")
                return "You do not have enough balance to complete this transfer."

            # --------------- STEP 3: UPDATE BALANCE IN SQLITE ----------------
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

            # --------------- STEP 4: INSERT TRANSACTION RECORD ----------------
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

            # --------------- STEP 4B: UPDATE RECEIVER BALANCE ----------------
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

            # --------------- STEP 5: UPDATE LAST TRANSACTION IN USER TABLE ----------------
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

            return (
                f"₹{amt_val} has been successfully sent to {recv_name} (Account: {recv_acc}). Transaction ID: {txn_id}",
                new_balance
            )

    # ---------- LOAN DOCUMENTS ----------
    loan_doc_phrases = [
        "documents required", "required documents", "loan documents",
        "what are the documents", "documents needed", "loan requirement",
        "requirements for loan",
    ]

    if any(p in low for p in loan_doc_phrases):
        return (
            "Documents required for any loan:\n"
            "• Aadhaar Card\n"
            "• PAN Card\n"
            "• 6 months bank statement\n"
            "• Salary slips / income proof\n"
            "• Address proof\n"
            "• Passport-size photo\n"
            "Note: Please visit the nearest branch or call customer care for more details."
        ) + intent_label("loan_documents")

    # ---------- LOAN INQUIRY ----------
    if "loan" in low and memory.get("last_domain") != "loan":
        memory["last_domain"] = "loan"
        return (
            "Available loans: Home, Personal, Car, Education, Business. "
            "Which loan would you like?"
        ) + intent_label("loan_inquiry")

    if memory.get("last_domain") == "loan" and not memory.get("loan_type"):
        for k in ["home", "personal", "car", "education", "business"]:
            if k in low:
                memory["loan_type"] = k
                return (
                    f"You chose {k.title()} Loan. Please enter your monthly income (numbers only)."
                ) + intent_label("loan_ask_income")

        return "Please choose one: Home, Personal, Car, Education, or Business." + intent_label(
            "loan_inquiry"
        )

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
            return (
                f"You are eligible for the {lt.title()} Loan (min monthly income required ₹{min_inc})."
            ) + intent_label("loan_approve")
        else:
            clear_domain("loan")
            return (
                f"Sorry, you are not eligible for the {lt.title()} Loan. Minimum required monthly income is ₹{min_inc}."
            ) + intent_label("loan_reject")

    # ---------- OPEN ACCOUNT ----------
    if any(w in low for w in ["open account", "new account", "create account"]):
        memory["last_domain"] = "open_account"
        return "Which type: Savings, Current, or Mutual?" + intent_label("open_account")

    if memory.get("last_domain") == "open_account" and any(w in low for w in ["savings", "current", "mutual"]):
        memory["open_account_type"] = (
            "savings" if "savings" in low else ("current" if "current" in low else "mutual")
        )
        return (
            "Eligibility: Aadhaar, PAN (if required), Mobile number. Please provide mobile then Aadhaar."
        ) + intent_label("account_eligibility")

    if memory.get("last_domain") == "open_account" and memory.get("mobile") and memory.get("aadhar"):
        new_acc = "ACNT" + str(random.randint(10000000, 99999999))
        clear_domain("open_account")
        return f"Your new account is created! Account number: {new_acc}." + intent_label(
            "provide_new_account"
        )

    # ---------- FEEDBACK ----------
    if any(w in low for w in ["drawback", "feedback", "problem", "issue", "not good"]):
        return "Thanks for the feedback — I'll try to improve." + intent_label("feedback")

    # ---------- OK / Affirmation ----------
    if low in ["ok", "okay", "k", "okk", "okayy", "fine", "alright", "hmm"]:
        return "Alright! How can I help you further?" + intent_label("acknowledge")

    # ---------- FALLBACK ----------
    return "Sorry, I didn’t understand that. Could you rephrase?" + intent_label("fallback")


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
        print("🟢 Bank Assistant:", reply)


if __name__ == "__main__":
    run_terminal()
