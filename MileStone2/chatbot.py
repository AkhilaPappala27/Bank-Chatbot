# chatbot.py
import re
import random
import sys

# ---------- Dummy DB (your data) ----------
ACCOUNTS = {
    "12W3335451": {"balance": 10000, "last": "₹500 credited by Ajay on 20/11/2025 07:00 AM"},
    "45A2390489": {"balance": 5000,  "last": "₹100 debited to Sravya on 21/11/2025 11:20 AM"},
    "78X1233490": {"balance": 123789,"last": "₹10,000 debited to Parvathi on 22/11/2025 04:31 PM"},
}
DEBIT_CARDS = ["123456789876", "123569044596"]
CREDIT_CARDS = ["850634784875", "908685755967"]
BLOCKED_CARDS=set()

# ---------- Session memory ----------
memory = {
    "account_number": None,
    "card_number": None,
    "card_type": None,
    "mobile": None,
    "aadhar": None,
    "last_domain": None,    # "balance", "transaction", "card", "card_block", "loan", "open_account"
    "need_reason": True,    # used for card_block
    "card_block_reason": None,
    "loan_type": None,
}

# ---------- Extractors ----------
def extract_account(text):
    m = re.search(r"\b[A-Z0-9]{10}\b", text.upper())
    return m.group(0) if m else None

def extract_card(text):
    m = re.search(r"\b\d{12}\b", text)
    return m.group(0) if m else None

def extract_mobile(text):
    # accepts 10-digit mobile (6-9 start typical for India)
    m = re.search(r"\b[6-9]\d{9}\b", text)
    return m.group(0) if m else None

def extract_aadhar(text):
    # remove spaces and non-digit, then look for 12 digits
    s = re.sub(r"\D", "", text)
    m = re.search(r"\b\d{12}\b", s)
    return m.group(0) if m else None

def extract_income(text):
    # look for numbers, assume monthly income in digits
    m = re.search(r"\b(?:rs\.?\s*)?(\d{3,9})\b", text.replace(',', ''))
    if m:
        return int(m.group(1))
    return None

# ---------- Helpers ----------
def clear_domain(domain):
    """Clear only domain-related keys after a domain completes"""
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

def intent_label(label):
    return f" ({label})"

# ---------- Bot logic ----------
def bot(user_input):
    text = user_input.strip()
    low = text.lower()

    # extract entities first and save to memory (supports "mobile and aadhar" in one message)
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

    if low in ["help", "what can you do", "options"]:
        return ("I can help with:\n"
            "- Check balance\n"
            "- Last transaction\n"
            "- New debit/credit card\n"
            "- Block/unblock card\n"
            "- Loan eligibility\n"
            "- Open new account\n"
            "Just tell me what you need!") + intent_label("help")


    # --- GREET (5 unique) ---
    if any(w in low for w in ["hi","hello","hey","hii","good morning","good afternoon","good evening"]):
        greetings = [
            "Hello! How can I assist you today?",
            "Hi there! What can I do for you?",
            "Hey! How may I help you today?",
            "Good day! How can I support you?",
            "Welcome! How can I make your banking easier?"
        ]
        return random.choice(greetings) + intent_label("greet")

    # --- THANKS ---
    if any(w in low for w in ["thank", "thanks", "thank you", "thx"]):
        replies = [
            "You're welcome!",
            "Glad I could help!",
            "Anytime — happy to assist.",
            "No problem — always here to help.",
            "My pleasure!"
        ]
        return random.choice(replies) + intent_label("thanks")

    # --- GOODBYE (variants) ---
    if any(w in low for w in ["bye", "byee", "byeee", "exit", "quit", "goodbye"]):
        return "Goodbye! Have a great day." + intent_label("goodbye")

    # STRICT OUT OF SCOPE — evaluate before greeting
    oos = ["movie", "movies", "recipe", "python", "weather", "news", "sports"]
    if any(w in low.split() for w in oos):
        return "I'm sorry — I can answer only banking-related questions." + intent_label("out_of_scope")

    # --- CHECK BALANCE ---
    if "balance" in low:
        memory["last_domain"] = "balance"
        if memory.get("account_number"):
            acc_no = memory["account_number"]
            acct = ACCOUNTS.get(acc_no)
            if acct:
                bal = acct["balance"]
                clear_domain("balance")
                return f"Your balance for account {acc_no} is ₹{bal}." + intent_label("provide_balance")
            clear_domain("balance")
            return "Invalid account number." + intent_label("fallback")
        return "Please provide your account number." + intent_label("check_balance")

    # when waiting for account after a balance request and user provides it now
    if memory.get("last_domain") == "balance" and memory.get("account_number"):
        acc_no = memory["account_number"]
        acct = ACCOUNTS.get(acc_no)
        if acct:
            bal = acct["balance"]
            clear_domain("balance")
            return f"Your balance for account {acc_no} is ₹{bal}." + intent_label("provide_balance")
        clear_domain("balance")
        return "Invalid account number." + intent_label("fallback")

    # --- TRANSACTION / LAST / PREVIOUS / LATEST ---
    txn_phrases = [
        "last transaction","last txn","previous transaction","previous txn",
        "latest transaction","recent transaction","transaction history","last transaction details",
        "previous transaction details","latest txn","recent txn"
    ]
    if any(p in low for p in txn_phrases):
        memory["last_domain"] = "transaction"
        if memory.get("account_number"):
            acc_no = memory["account_number"]
            acct = ACCOUNTS.get(acc_no)
            if acct:
                last = acct["last"]
                clear_domain("transaction")
                return f"Your last transaction for account {acc_no}: {last}" + intent_label("transaction_inquiry")
            clear_domain("transaction")
            return "Invalid account number." + intent_label("fallback")
        return "Please provide your account number first." + intent_label("transaction_inquiry")

    if memory.get("last_domain") == "transaction" and memory.get("account_number"):
        acc_no = memory["account_number"]
        acct = ACCOUNTS.get(acc_no)
        if acct:
            last = acct["last"]
            clear_domain("transaction")
            return f"Your last transaction for account {acc_no}: {last}" + intent_label("transaction_inquiry")
        clear_domain("transaction")
        return "Invalid account number." + intent_label("fallback")

        # ---------------- NEW CARD REQUEST ----------------
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

    # When user provides numbers in card flow
    if memory.get("last_domain") == "card" and memory.get("card_type"):

        mobile = extract_mobile(text)
        aadhar = extract_aadhar(text)

        # store only if present
        if mobile:
            memory["mobile"] = mobile
        if aadhar:
            memory["aadhar"] = aadhar

        # If both present → issue card
        if memory.get("mobile") and memory.get("aadhar"):
            if memory["card_type"] == "debit":
                cardnum = random.choice(DEBIT_CARDS)
                clear_domain("card")
                return f"Your debit card request is approved! Card number: {cardnum}."

            elif memory["card_type"] == "credit":
                cardnum = random.choice(CREDIT_CARDS)
                clear_domain("card")
                return f"Your credit card request is approved! Card number: {cardnum}."

        # If only mobile present
        if memory.get("mobile") and not memory.get("aadhar"):
            return "Mobile number received. Now provide your 12-digit Aadhaar number."

        # If only Aadhaar present
        if memory.get("aadhar") and not memory.get("mobile"):
            return "Aadhaar received. Now provide your 10-digit mobile number."

        return "Please provide your 10-digit mobile and 12-digit Aadhaar numbers."

    # ---------------- BLOCK CARD ----------------
    if re.search(r"\bblock\b", low) and not re.search(r"\bunblock\b", low):
        memory["last_domain"] = "block_card"

        # If the message already contains a card number
        card = extract_card(text)
        if card:
            if card in BLOCKED_CARDS:
                memory["last_domain"] = None
                return f"Card {card} is already blocked." + intent_label("card_already_blocked")

            BLOCKED_CARDS.add(card)
            memory["last_domain"] = None
            return f"Card {card} has been blocked successfully." + intent_label("block_card_success")

        return "Please provide your 12-digit card number to block the card." + intent_label("ask_block_card_number")

    # Waiting for card number for blocking
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



    # ---------------- UNBLOCK CARD ----------------
    if re.search(r"\bunblock\b", low) or re.search(r"\bactivate\b", low) or "unblockcard" in low.replace(" ", ""):
        memory["last_domain"] = "unblock_card"

        # If card number is already present in the same message
        card = extract_card(text)
        if card:
            if card not in BLOCKED_CARDS:
                memory["last_domain"] = None
                return f"Card {card} is already active (not blocked)." + intent_label("card_not_blocked")

            BLOCKED_CARDS.remove(card)
            memory["last_domain"] = None
            return f"Card {card} has been unblocked successfully." + intent_label("unblock_card_success")

        return "Please provide your 12-digit card number to unblock the card." + intent_label("ask_unblock_card")


    # Waiting for card number for unblocking
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

    # --- LOAN DOCUMENT REQUIREMENTS ---
    loan_doc_phrases = ["documents required", "required documents", "loan documents",
                    "what are the documents", "documents needed", "loan requirement",
                    "requirements for loan"]

    if any(p in low for p in loan_doc_phrases):
        return ("Documents required for any loan:\n"
            "• Aadhaar Card\n"
            "• PAN Card\n"
            "• 6 months bank statement\n"
            "• Salary slips / income proof\n"
            "• Address proof\n"
            "• Passport-size photo\n"
            "Note: Please visit the nearest branch or call customer care for more details."
            ) + intent_label("loan_documents")


    # ---------------- LOAN INQUIRY ----------------
    if "loan" in low and memory.get("last_domain") != "loan":
        memory["last_domain"] = "loan"
        return ("Available loans: Home, Personal, Car, Education, Business. "
                "Which loan would you like?") + intent_label("loan_inquiry")

    # If in loan flow and user chooses loan type
    if memory.get("last_domain") == "loan" and not memory.get("loan_type"):
        for k in ["home", "personal", "car", "education", "business"]:
            if k in low:
                memory["loan_type"] = k
                # ask income for eligibility
                return f"You chose {k.title()} Loan. Please enter your monthly income (numbers only)." + intent_label("loan_ask_income")
        # user hasn't chosen a known loan type
        return "Please choose one: Home, Personal, Car, Education, or Business." + intent_label("loan_inquiry")

    # If loan type selected and waiting income
    if memory.get("last_domain") == "loan" and memory.get("loan_type") and inc is not None:
        # define simple minimum income thresholds per loan type (monthly)
        thresholds = {
            "home": 40000,
            "personal": 20000,
            "car": 25000,
            "education": 15000,
            "business": 30000
        }
        lt = memory.get("loan_type")
        min_inc = thresholds.get(lt, 20000)
        if inc >= min_inc:
            clear_domain("loan")
            return f"You are eligible for the {lt.title()} Loan (min monthly income required ₹{min_inc})." + intent_label("loan_approve")
        else:
            clear_domain("loan")
            return f"Sorry, you are not eligible for the {lt.title()} Loan. Minimum required monthly income is ₹{min_inc}." + intent_label("loan_reject")

    # ---------------- OPEN ACCOUNT ----------------
    if any(w in low for w in ["open account", "new account", "create account"]):
        memory["last_domain"] = "open_account"
        return "Which type: Savings, Current, or Mutual?" + intent_label("open_account")

    if memory.get("last_domain") == "open_account" and any(w in low for w in ["savings","current","mutual"]):
        memory["open_account_type"] = "savings" if "savings" in low else ("current" if "current" in low else "mutual")
        return "Eligibility: Aadhaar, PAN (if required), Mobile number. Please provide mobile then Aadhaar." + intent_label("account_eligibility")

    if memory.get("last_domain") == "open_account" and memory.get("mobile") and memory.get("aadhar"):
        new_acc = "ACNT" + str(random.randint(10000000,99999999))
        clear_domain("open_account")
        return f"Your new account is created! Account number: {new_acc}." + intent_label("provide_new_account")

    # ---------------- FEEDBACK / OUT OF SCOPE ----------------
    if any(w in low for w in ["drawback","feedback","problem","issue","not good"]):
        return "Thanks for the feedback — I'll try to improve." + intent_label("feedback")
    
    # --- OK / Affirmation ---
    if low in ["ok", "okay", "k", "okk", "okayy", "fine", "alright", "hmm"]:
        return "Alright! How can I help you further?" + intent_label("acknowledge")

    # ---------------- FALLBACK ----------------
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

        # user explicit exit variants (instant quit)
        if user.lower() in ("bye", "byee", "byeee", "exit", "quit", "goodbye"):
            print("🟢 Bank Assistant: Goodbye! Have a great day. (goodbye)")
            break

        reply = bot(user)
        print("🟢 Bank Assistant:", reply)

if __name__ == "__main__":
    run_terminal()
