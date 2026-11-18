"""Hand-written varied phrasing templates for the 150-ticket synthetic evaluation set.

All product names, order numbers, cities, and scenarios belong to the fictional
Kora Living e-commerce demonstration workspace.
"""

from __future__ import annotations

PRODUCTS = [
    "Terracotta Table Lamp",
    "Stoneware Dinner Set",
    "Handwoven Jute Rug",
    "Brass Floor Lamp",
    "Linen Duvet Cover",
    "Ceramic Pour-Over Carafe",
    "Walnut Serving Tray",
    "Cotton Throw Blanket",
    "Matte Ceramic Planter",
    "Rattan Accent Basket",
    "Fluted Glass Tumbler Set",
    "Acacia Chopping Board",
    "Block-Print Cushion Cover Set",
    "Enamel Kettle",
]

CITIES = [
    "Bengaluru",
    "Mumbai",
    "Pune",
    "Hyderabad",
    "Jaipur",
    "Chennai",
    "Kochi",
    "Ahmedabad",
    "Gurugram",
    "Kolkata",
    "Chandigarh",
    "Indore",
]

DATES = [
    "14 Sep",
    "19 Sep",
    "24 Sep",
    "2 Oct",
    "7 Oct",
    "11 Oct",
    "16 Oct",
    "21 Oct",
    "25 Oct",
    "28 Oct",
]

CHANNELS = ["email", "chat", "web_form", "whatsapp"]

# At least 8 distinct hand-written English phrasings per category.
# Each tuple: (subject_template, body_template, signals_list)
CATEGORY_TEMPLATES: dict[str, list[tuple[str, str, list[str]]]] = {
    "order_tracking": [
        (
            "Where is my {product} order {order_id}?",
            "Hi team, I ordered the {product} under {order_id} on {date} for delivery to {city}. The courier tracking page has not moved for four days now and still shows sitting at the hub. Could you check when it will actually arrive?",
            ["delivery_delayed_over_3_days"],
        ),
        (
            "Urgent delivery check for {order_id}",
            "Hello, my {product} ({order_id}) was supposed to reach {city} by {date} and is already five days overdue. I need this urgently for a housewarming dinner tomorrow evening. Please escalate with the courier right away.",
            ["delivery_delayed_over_3_days", "explicit_urgency"],
        ),
        (
            "Tracking link stuck on manifested — {order_id}",
            "Good afternoon, I placed order {order_id} on {date} for a {product}. The tracking link has been frozen on shipment manifested since dispatch, which is over four days late now. Can someone share a real update?",
            ["delivery_delayed_over_3_days"],
        ),
        (
            "No tracking update yet for {order_id}",
            "Hi Kora Living support, I bought the {product} yesterday ({order_id}) and haven't received an AWB number or tracking link yet. Could you let me know when it is scheduled to ship to {city}?",
            ["general_inquiry"],
        ),
        (
            "Need {product} before Friday — order {order_id}",
            "Hi, I ordered the {product} ({order_id}) and I am travelling out of {city} on Friday morning. Can you confirm whether the parcel will be delivered before then? It is quite time-sensitive.",
            ["explicit_urgency"],
        ),
        (
            "Courier marked attempted delivery without calling ({order_id})",
            "My tracking for {order_id} ({product}) suddenly says delivery attempted in {city}, even though I was home all day and nobody rang. This parcel is already four days past the estimated date. Please arrange redelivery.",
            ["delivery_delayed_over_3_days"],
        ),
        (
            "Partial shipment received for {order_id}",
            "Hello, only part of my order {order_id} arrived in {city} on {date}, and the {product} is still missing from the tracking portal. Can you confirm if it was split into a second box?",
            ["general_inquiry"],
        ),
        (
            "Over a week late and no response — {order_id}",
            "I ordered the {product} ({order_id}) on {date} and it is still stuck in transit to {city} more than a week past the promised window. If I do not get a confirmed delivery date today I am filing a chargeback with my bank.",
            ["delivery_delayed_over_3_days", "legal_or_chargeback_threat"],
        ),
        (
            "Gift order {order_id} running late",
            "Hi support, order {order_id} for the {product} was meant to be an anniversary gift in {city}. It is now four days past the delivery estimate and we need it urgently before the weekend.",
            ["delivery_delayed_over_3_days", "explicit_urgency"],
        ),
    ],
    "returns_refunds": [
        (
            "Return pickup request for {product} ({order_id})",
            "Hi, I received my {product} from order {order_id} on {date} in {city}. The colour looks darker than expected in my living room, so I would like to return it unused in the original box. How do I schedule pickup?",
            ["general_inquiry"],
        ),
        (
            "Refund still not credited after return — {order_id}",
            "Hello team, the courier picked up my returned {product} ({order_id}) two weeks ago and tracking confirms it reached your warehouse. It has been over ten business days and the refund is still overdue on my card.",
            ["refund_overdue"],
        ),
        (
            "Exchange size for {product} on {order_id}",
            "Good morning, I bought the {product} ({order_id}) delivered on {date} and would like to return it for a different size because it doesn't fit our dining table. Tags and packaging are completely intact.",
            ["general_inquiry"],
        ),
        (
            "Reverse pickup keeps getting rescheduled ({order_id})",
            "I requested a return for the {product} ({order_id}) in {city} on {date}, and the courier has cancelled pickup three times. I am leaving town urgently in two days and need this collected before I go.",
            ["explicit_urgency"],
        ),
        (
            "Still waiting on COD refund for {order_id}",
            "Hi, I returned my COD order {order_id} ({product}) on {date} and submitted my UPI details through the payout link. More than nine business days have passed and the refund still hasn't arrived.",
            ["refund_overdue"],
        ),
        (
            "Return window question for {order_id}",
            "Hello, my {product} from order {order_id} was delivered to {city} three days ago. It is unopened and I would like to initiate a return back to my original payment method.",
            ["general_inquiry"],
        ),
        (
            "Overdue refund — escalating to consumer forum ({order_id})",
            "My returned {product} ({order_id}) was inspected at your warehouse weeks ago and I still have no refund in my bank account. If this overdue refund is not processed immediately, I will lodge a consumer court complaint.",
            ["refund_overdue", "legal_or_chargeback_threat"],
        ),
        (
            "Wrong refund amount received for {order_id}",
            "Hi support, I returned two units of the {product} under {order_id} on {date}, yet only a partial refund came through and the remaining balance is now overdue past seven business days. Please check.",
            ["refund_overdue"],
        ),
    ],
    "payment_issues": [
        (
            "Charged twice on my card for {order_id}",
            "Hi, I just placed order {order_id} for the {product} and my credit card statement shows two identical deductions for the exact same order. Please reverse the duplicate charge as soon as possible.",
            ["payment_charged_twice"],
        ),
        (
            "UPI money deducted but order failed — {product}",
            "Hello, I tried buying the {product} on {date} via UPI. The amount was debited from my bank account immediately, but the Kora Living checkout page crashed and no order confirmation appeared in my account.",
            ["payment_deducted_order_failed"],
        ),
        (
            "Duplicate billing alert for {order_id}",
            "Good evening, I checked my bank app after purchasing the {product} ({order_id}) and noticed I was billed twice within one minute. Can your payments team confirm the extra charge will be reversed?",
            ["payment_charged_twice"],
        ),
        (
            "Payment failed yet funds debited on {date}",
            "Hi team, during checkout for the {product} to {city}, net banking deducted the full amount and then redirected to a payment-failed screen. I don't have an order ID and need the reversal checked urgently.",
            ["payment_deducted_order_failed", "explicit_urgency"],
        ),
        (
            "Double charge still not reversed — will dispute with bank",
            "I was charged twice for my {product} ({order_id}) on {date} and it has still not been reversed. If your payments team does not resolve this today, I am initiating a chargeback with my card issuer.",
            ["payment_charged_twice", "legal_or_chargeback_threat"],
        ),
        (
            "Invoice GST breakdown request for {order_id}",
            "Hello, could you email a revised tax invoice showing the GST split for my {product} purchase ({order_id}) from {date}? Everything on the order itself was fine.",
            ["general_inquiry"],
        ),
        (
            "Promo code didn't apply before card charge ({order_id})",
            "Hi, I entered the welcome code while ordering the {product} ({order_id}) on {date}, and the final total charged full price. Is there any way to adjust the discount or clarify eligibility?",
            ["general_inquiry"],
        ),
        (
            "Debited twice during checkout retry for {order_id}",
            "The checkout screen froze while paying for my {product} ({order_id}), so I clicked pay again. Now both transactions went through on my debit card. Please help refund the duplicate payment.",
            ["payment_charged_twice"],
        ),
    ],
    "product_questions": [
        (
            "Care instructions for {product}",
            "Hi Kora Living, I am considering ordering the {product} for our apartment in {city}. Could you tell me if it is safe to wipe with a damp cloth or if it requires dry cleaning only?",
            ["general_inquiry"],
        ),
        (
            "Dimensions and weight of {product}",
            "Hello, the product page for the {product} doesn't list the exact base diameter or total weight. Could you share the measurements before I place my order?",
            ["general_inquiry"],
        ),
        (
            "Restock timeline for {product}",
            "Hi team, the {product} in warm sand has been out of stock since {date}. Do you know when it will be restocked so I can order it to {city}?",
            ["general_inquiry"],
        ),
        (
            "Material sourcing question — {product}",
            "Good afternoon, is the {product} food-safe and lead-free for everyday kitchen use? I want to be sure before buying a set for my family.",
            ["general_inquiry"],
        ),
        (
            "Bulk gifting quote needed urgently for {product}",
            "Hello, our office in {city} wants to order several units of the {product} for a client event next week and we need to confirm stock availability urgently today.",
            ["explicit_urgency"],
        ),
        (
            "Compatibility question about {product}",
            "Hi, does the {product} work with standard Indian wall sockets and warm LED bulbs, or does it need a specialty fitting?",
            ["general_inquiry"],
        ),
        (
            "Colour match inquiry for {product}",
            "Hello, I already own your stoneware pieces and want to know if the {product} matches the matte ivory glaze or leans more cream.",
            ["general_inquiry"],
        ),
        (
            "Outdoor suitability of {product}",
            "Can the {product} be placed on a covered balcony in {city} during the monsoon, or is it strictly meant for indoor rooms?",
            ["general_inquiry"],
        ),
    ],
    "address_change": [
        (
            "Update delivery address before dispatch — {order_id}",
            "Hi team, I just placed order {order_id} for the {product} a few minutes ago and accidentally left my old flat number in {city}. Could you update the shipping address before it leaves the warehouse?",
            ["explicit_urgency"],
        ),
        (
            "Wrong pin code entered on {order_id}",
            "Hello, I noticed a typo in the pin code on my order {order_id} ({product}). Since it has not been dispatched yet, can you correct the address right away?",
            ["explicit_urgency"],
        ),
        (
            "Change delivery phone number on {order_id}",
            "Hi support, I ordered the {product} ({order_id}) on {date} as a gift for my sister in {city} and put my own mobile number by mistake. Can we switch the recipient contact number?",
            ["general_inquiry"],
        ),
        (
            "Switch shipping to office address ({order_id})",
            "Good morning, nobody will be at our apartment during weekday afternoons in {city}. Can I redirect order {order_id} ({product}) to my office address before dispatch?",
            ["general_inquiry"],
        ),
        (
            "Urgent address correction needed for {order_id}",
            "Please hold dispatch on {order_id} ({product})! Autofill put my previous city instead of {city}. I need the shipping address updated urgently before the courier picks it up.",
            ["explicit_urgency"],
        ),
        (
            "Missing apartment landmark on {order_id}",
            "Hi, I forgot to include the tower name and gate code on order {order_id} for the {product}. Could you add those delivery instructions to the shipping label?",
            ["general_inquiry"],
        ),
        (
            "Can I change delivery address after dispatch ({order_id})?",
            "Hello, my {product} ({order_id}) already shows dispatched to {city}. I just had to travel unexpectedly — is there any option to reroute the shipment to my parents' address?",
            ["general_inquiry"],
        ),
        (
            "Move delivery to neighbour's flat for {order_id}",
            "Hi Kora Living, I placed {order_id} on {date} for the {product}. Before it ships out, could you update the flat number on the delivery address?",
            ["general_inquiry"],
        ),
    ],
    "damaged_item": [
        (
            "Broken {product} arrived today — {order_id}",
            "Hi team, my {product} from order {order_id} was delivered to {city} this morning, and when I opened the box the ceramic base was cracked cleanly in two. I have photos of the item and box ready to send for a replacement.",
            ["item_damaged_or_defective"],
        ),
        (
            "Received wrong item in parcel {order_id}",
            "Hello, I ordered the {product} under {order_id}, but the box that arrived in {city} on {date} contained a completely different cushion set instead. Please arrange a pickup and send the correct item.",
            ["wrong_item_received"],
        ),
        (
            "Chipped rim and scratched finish on {product} ({order_id})",
            "Good afternoon, the {product} I received today ({order_id}) has a visible chip along the rim and deep scratches across the glaze. I am reporting this within hours of delivery and would like a free replacement.",
            ["item_damaged_or_defective"],
        ),
        (
            "Defective switch on {product} — {order_id}",
            "Hi support, my {product} ({order_id}) arrived in {city} yesterday, and the power switch flickers and refuses to stay on. The wiring looks defective out of the box. Please replace it.",
            ["item_damaged_or_defective"],
        ),
        (
            "Wrong colour and size sent for {order_id}",
            "I ordered the {product} ({order_id}) on {date}, yet the label inside shows a different colour and smaller dimension than what is on my invoice. Please swap it for the item I actually paid for.",
            ["wrong_item_received"],
        ),
        (
            "Shattered parcel delivered — need urgent replacement ({order_id})",
            "My {product} ({order_id}) arrived completely shattered in {city} just now. I need a replacement urgently before guests arrive this weekend. I can share photos of the damaged box immediately.",
            ["item_damaged_or_defective", "explicit_urgency"],
        ),
        (
            "Damaged {product} and nobody replied — legal notice next",
            "Order {order_id} arrived cracked on {date} and I sent photos right away. If I do not receive a replacement or full refund for this damaged {product}, I will file a consumer complaint and chargeback.",
            ["item_damaged_or_defective", "legal_or_chargeback_threat"],
        ),
        (
            "Stained textile delivered in {order_id}",
            "Hello, I unboxed the {product} ({order_id}) delivered today in {city} and found dark oil stains across the fabric even though the outer carton looked fine. Requesting a replacement.",
            ["item_damaged_or_defective"],
        ),
    ],
    "account_login": [
        (
            "Locked out of my Kora Living account",
            "Hi support, I tried signing in to check my {product} order history and after a few wrong passwords my account says it is locked. I cannot access my orders at all.",
            ["account_locked"],
        ),
        (
            "Password reset email not arriving",
            "Hello, I clicked forgot password three times over the past hour to unlock my account, checked spam and promotions, and still have not received any reset link.",
            ["account_locked"],
        ),
        (
            "OTP login failing repeatedly",
            "Hi team, every time I enter my mobile number to log in to Kora Living, the OTP either expires immediately or says my account is temporarily locked. Please help restore access.",
            ["account_locked"],
        ),
        (
            "Account locked while trying to place urgent order",
            "I am locked out of my account right when I need to urgently check out a gift order for a {product} to {city}. Password reset keeps looping back to the error screen.",
            ["account_locked", "explicit_urgency"],
        ),
        (
            "How do I update my registered email address?",
            "Good morning, I can still sign in to my Kora Living profile, and I would like to change my saved email address before placing my next order. Where is that option in settings?",
            ["general_inquiry"],
        ),
        (
            "Cannot sign in to download invoice for {order_id}",
            "Hi, my account has been locked since {date} and I need to log in to download the GST invoice for order {order_id} ({product}). Resetting the password didn't unlock it.",
            ["account_locked"],
        ),
        (
            "Unsubscribe from promotional emails",
            "Hello, I love your {product} collection, though I'm getting too many marketing newsletters each week. Could you help me opt out of promo emails without closing my account?",
            ["general_inquiry"],
        ),
        (
            "Sign-in error after changing phone number",
            "Hi team, I got a new mobile number in {city} and now my Kora Living account is locked because two-step login sends the code to my old SIM. Can you help me regain access?",
            ["account_locked"],
        ),
    ],
}

# Hand-written Hinglish tickets (language="hinglish", >= 10 required -> we provide 14).
# Tuple: (true_category, subject, body, signals, is_ambiguous, secondary_category)
HINGLISH_TICKETS: list[tuple[str, str, str, list[str], bool, str | None]] = [
    (
        "order_tracking",
        "Mera order {order_id} abhi tak nahi aaya",
        "Hi team, maine {date} ko {product} order kiya tha {city} ke liye ({order_id}). Tracking 4 din se ek hi jagah atka hua hai, please jaldi check karo kab deliver hoga.",
        ["delivery_delayed_over_3_days"],
        False,
        None,
    ),
    (
        "order_tracking",
        "Delivery bahut late ho gayi hai {order_id}",
        "Hello, {order_id} ({product}) kal function ke liye chahiye tha aur already 5 din delay ho chuka hai. Bahut urgent hai bhai, courier se baat karke aaj deliver karwao.",
        ["delivery_delayed_over_3_days", "explicit_urgency"],
        False,
        None,
    ),
    (
        "returns_refunds",
        "Refund abhi tak bank mein nahi aaya ({order_id})",
        "Namaste, mera {product} ({order_id}) return pickup hoke warehouse pahunch gaya tha {date} ko. Abhi tak refund credit nahi hua hai, 8 din se zyada ho gaye.",
        ["refund_overdue"],
        False,
        None,
    ),
    (
        "returns_refunds",
        "Return pickup kab hoga {order_id} ka?",
        "Hi, {product} ({order_id}) ka size room mein fit nahi ho raha. Box bilkul packed hai, return pickup schedule kar dijiye {city} mein.",
        ["general_inquiry"],
        False,
        None,
    ),
    (
        "payment_issues",
        "UPI se do baar paise kat gaye {order_id}",
        "Hello support, maine {product} ke liye payment kiya ({order_id}) aur mere bank se do baar amount deduct ho gaya hai. Please extra payment jaldi reverse karwaiye.",
        ["payment_charged_twice"],
        False,
        None,
    ),
    (
        "payment_issues",
        "Paise kat gaye par order confirm nahi hua",
        "Hi, aaj {product} order kar raha tha {city} ke liye. UPI se paise cut ho gaye lekin website pe error aa gaya aur koi order ID nahi mili.",
        ["payment_deducted_order_failed"],
        False,
        None,
    ),
    (
        "damaged_item",
        "Toota hua {product} mila hai {order_id}",
        "Hi Kora Living, aaj subah {order_id} deliver hua aur box khola toh {product} poora crack nikla. Maine photos le li hain, replacement bhej dijiye please.",
        ["item_damaged_or_defective"],
        False,
        None,
    ),
    (
        "damaged_item",
        "Galat product bhej diya {order_id} mein",
        "Hello, maine {product} mangwaya tha ({order_id}) par parcel mein koi aur item aa gaya hai {city} mein. Please sahi item bhejo aur yeh wapas le jao.",
        ["wrong_item_received"],
        False,
        None,
    ),
    (
        "address_change",
        "Address change karna hai dispatch se pehle ({order_id})",
        "Hi, abhi just {order_id} ({product}) place kiya hai aur galat flat number dal gaya. Urgent hai, dispatch hone se pehle address update kar do please.",
        ["explicit_urgency"],
        False,
        None,
    ),
    (
        "account_login",
        "Account login nahi ho raha, lock ho gaya",
        "Hello team, password reset karne ke baad bhi mera account locked dikha raha hai. OTP bhi nahi aa raha {city} mein, login fix kar dijiye.",
        ["account_locked"],
        False,
        None,
    ),
    (
        "product_questions",
        "{product} ka exact size aur material bataiye",
        "Hi, {product} wash kar sakte hain kya aur kya yeh {city} mein stock mein hai? Lene se pehle confirm karna tha.",
        ["general_inquiry"],
        False,
        None,
    ),
    (
        "order_tracking",
        "Parcel late aur address bhi update karna tha ({order_id})",
        "Hi, mera {product} ({order_id}) already 4 din late chal raha hai aur ab main {city} se bahar ja raha hoon toh address change ho sakta hai kya?",
        ["delivery_delayed_over_3_days"],
        True,
        "address_change",
    ),
    (
        "payment_issues",
        "Double charge hua hai, warna bank dispute karunga ({order_id})",
        "Maine {date} ko {product} ({order_id}) liya aur card do baar charge ho gaya. Aaj solve nahi hua toh bank mein chargeback raise kar dunga.",
        ["payment_charged_twice", "legal_or_chargeback_threat"],
        False,
        None,
    ),
    (
        "returns_refunds",
        "Damaged item return kiya par refund nahi aaya ({order_id})",
        "Mera {product} ({order_id}) damaged aaya tha, return pickup bhi ho gaya par refund abhi tak overdue hai. Please status batao.",
        ["refund_overdue", "item_damaged_or_defective"],
        True,
        "damaged_item",
    ),
]

# Hand-written ambiguous dual-category English tickets (>= 15 total ambiguous required).
# Tuple: (true_category, secondary_category, subject, body, signals)
AMBIGUOUS_TICKETS: list[tuple[str, str, str, str, list[str]]] = [
    (
        "damaged_item",
        "returns_refunds",
        "Cracked {product} — want full refund instead of exchange ({order_id})",
        "My {product} from {order_id} arrived cracked along the handle in {city} today. Rather than waiting for a replacement, I would prefer to return it for a full refund to my original card.",
        ["item_damaged_or_defective"],
    ),
    (
        "order_tracking",
        "address_change",
        "Delayed parcel {order_id} — need delivery redirected",
        "Order {order_id} ({product}) is now four days overdue to {city}, and because it missed the delivery window I will be away from home. Can you trace the parcel and redirect it to my office?",
        ["delivery_delayed_over_3_days"],
    ),
    (
        "returns_refunds",
        "payment_issues",
        "Returned {product} and charged twice? ({order_id})",
        "I returned my {product} ({order_id}) on {date} and am still waiting on the overdue refund, plus my bank statement looks like the order was billed twice. Please sort out both.",
        ["refund_overdue", "payment_charged_twice"],
    ),
    (
        "payment_issues",
        "order_tracking",
        "Payment deducted on {date} — did my {product} ship?",
        "Money was debited from my UPI account for the {product}, yet I cannot see any order number or tracking update in my dashboard. Did the order go through or fail?",
        ["payment_deducted_order_failed"],
    ),
    (
        "account_login",
        "order_tracking",
        "Locked out while trying to track {order_id}",
        "My Kora Living account is locked and password reset isn't working, which means I cannot check where my delayed {product} ({order_id}) is. Please unlock my login and share tracking.",
        ["account_locked", "delivery_delayed_over_3_days"],
    ),
    (
        "damaged_item",
        "product_questions",
        "Scratched {product} — is this normal finish? ({order_id})",
        "I just unboxed the {product} ({order_id}) in {city} and there is a long dent and rough crack on one side. Is this handmade variation or a defective piece I should replace?",
        ["item_damaged_or_defective"],
    ),
    (
        "address_change",
        "order_tracking",
        "Need to fix address on {order_id} before courier ships",
        "I ordered the {product} ({order_id}) for a birthday in {city} and put the wrong street name. Tracking hasn't updated yet, so can you confirm dispatch status and edit the address urgently?",
        ["explicit_urgency"],
    ),
    (
        "returns_refunds",
        "damaged_item",
        "Wrong colour received — requesting return pickup ({order_id})",
        "The {product} delivered under {order_id} on {date} is the wrong item compared to my invoice. Please initiate a return pickup and confirm when my refund will process.",
        ["wrong_item_received"],
    ),
    (
        "payment_issues",
        "account_login",
        "Locked out after duplicate card charge ({order_id})",
        "My card was charged twice for {order_id} ({product}), and when I tried signing back in to check the invoice my account locked out. I need the double charge reversed first.",
        ["payment_charged_twice", "account_locked"],
    ),
    (
        "product_questions",
        "returns_refunds",
        "If {product} doesn't match my decor, can I return it?",
        "Before ordering the {product} to {city}, could you confirm the exact fabric shade and whether it qualifies for your seven-day return window if it clashes with my sofa?",
        ["general_inquiry"],
    ),
    (
        "order_tracking",
        "returns_refunds",
        "Cancel and refund late shipment {order_id}",
        "My {product} ({order_id}) has been stuck in transit to {city} for five days past the expected delivery date. At this point I need it cancelled or returned once it arrives because the event passed.",
        ["delivery_delayed_over_3_days"],
    ),
    (
        "damaged_item",
        "order_tracking",
        "Box arrived crushed and missing second {product} ({order_id})",
        "Order {order_id} finally reached {city} after a four-day delay, and the outer carton was crushed with one broken {product} inside and the second unit missing.",
        ["item_damaged_or_defective", "delivery_delayed_over_3_days"],
    ),
    (
        "returns_refunds",
        "account_login",
        "Can't log in to track my overdue refund ({order_id})",
        "My refund for the returned {product} ({order_id}) is past seven business days, and my account is also locked so I cannot check the return portal status.",
        ["refund_overdue", "account_locked"],
    ),
    (
        "address_change",
        "product_questions",
        "Change address on {order_id} and check bulb type",
        "Please urgently update the shipping address on {order_id} ({product}) to my new flat in {city} before dispatch, and also let me know which LED bulb wattage fits it.",
        ["explicit_urgency"],
    ),
    (
        "payment_issues",
        "returns_refunds",
        "Failed checkout charge vs return credit ({order_id})",
        "I had a failed payment deducted on {date} for the {product} and separately returned an earlier item ({order_id}). Neither amount has returned to my bank yet.",
        ["payment_deducted_order_failed", "refund_overdue"],
    ),
    (
        "product_questions",
        "order_tracking",
        "Will {product} reach {city} by Saturday if ordered today?",
        "I want to buy the {product} for a Saturday dinner in {city} — can you confirm the lamp dimensions and whether standard shipping can realistically deliver urgently in time?",
        ["explicit_urgency"],
    ),
    (
        "order_tracking",
        "damaged_item",
        "Courier says parcel {order_id} damaged in transit",
        "Tracking for my {product} ({order_id}) to {city} has been delayed over four days and now shows a courier exception saying the carton was damaged at the sorting hub.",
        ["delivery_delayed_over_3_days", "item_damaged_or_defective"],
    ),
]

# Hand-written very short messages (< 12 words each, >= 10 required -> we provide 14).
# Tuple: (true_category, subject, body, signals, language)
SHORT_TICKETS: list[tuple[str, str, str, list[str], str]] = [
    ("order_tracking", "Order {order_id}", "Order {order_id} is five days late. Where is it?", ["delivery_delayed_over_3_days"], "en"),
    ("order_tracking", "Tracking {order_id}", "Need {order_id} delivered urgently by tomorrow morning please.", ["explicit_urgency"], "en"),
    ("returns_refunds", "Return {order_id}", "Want to return {product} from order {order_id}.", ["general_inquiry"], "en"),
    ("returns_refunds", "Refund {order_id}", "Refund for {order_id} is overdue two weeks now.", ["refund_overdue"], "en"),
    ("payment_issues", "Double charge", "Charged twice for order {order_id}. Please reverse immediately.", ["payment_charged_twice"], "en"),
    ("payment_issues", "Payment failed", "UPI deducted on {date} but order failed.", ["payment_deducted_order_failed"], "en"),
    ("damaged_item", "Broken item", "{product} in {order_id} arrived broken today.", ["item_damaged_or_defective"], "en"),
    ("damaged_item", "Wrong item", "Received wrong product in order {order_id}.", ["wrong_item_received"], "en"),
    ("address_change", "Fix address", "Urgent: change shipping address on {order_id} before dispatch.", ["explicit_urgency"], "en"),
    ("address_change", "Pin code typo", "Wrong pin code on {order_id}, please update.", ["general_inquiry"], "en"),
    ("account_login", "Account locked", "My Kora Living account is locked, cannot login.", ["account_locked"], "en"),
    ("account_login", "No reset mail", "Password reset email not coming, still locked out.", ["account_locked"], "en"),
    ("product_questions", "Size check", "What are the dimensions of {product}?", ["general_inquiry"], "en"),
    ("product_questions", "Washable?", "Is the {product} machine washable?", ["general_inquiry"], "en"),
]
