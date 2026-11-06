"""Worker- and supervisor-facing text in English, Urdu, Arabic and Hindi.

Translations are written for clarity at a basic reading level and should be
reviewed by native speakers before a real pilot.
"""

LANGS = {"en": "English", "ur": "اردو", "ar": "العربية", "hi": "हिन्दी"}

LEVEL_NAMES = {
    "en": ["Low", "Caution", "High", "Extreme"],
    "ur": ["کم", "احتیاط", "زیادہ خطرہ", "شدید خطرہ"],
    "ar": ["منخفض", "حذر", "مرتفع", "شديد"],
    "hi": ["कम", "सावधानी", "उच्च", "अत्यधिक"],
}

ACTIONS = {
    "en": [
        "Drink water regularly and know the signs of heat illness.",
        "Drink a cup of water every 15–20 minutes, take shade breaks, and watch your work partner.",
        "Rest in the shade more often, reduce heavy work, drink water every 15 minutes, and follow your supervisor's break schedule.",
        "Stop non-essential heavy work now. Move to shade, drink water, and only continue essential tasks with strict rest breaks.",
    ],
    "ur": [
        "باقاعدگی سے پانی پیتے رہیں اور گرمی سے بیماری کی علامات پر نظر رکھیں۔",
        "ہر 15–20 منٹ میں ایک کپ پانی پیئیں، سائے میں وقفہ لیں، اور اپنے ساتھی کا خیال رکھیں۔",
        "سائے میں زیادہ آرام کریں، بھاری کام کم کریں، ہر 15 منٹ پانی پیئیں، اور سپروائزر کے وقفوں کے شیڈول پر عمل کریں۔",
        "غیر ضروری بھاری کام ابھی روک دیں۔ سائے میں جائیں، پانی پیئیں، اور صرف ضروری کام سخت وقفوں کے ساتھ کریں۔",
    ],
    "ar": [
        "اشرب الماء بانتظام وتعرّف على علامات الإجهاد الحراري.",
        "اشرب كوب ماء كل 15–20 دقيقة، وخذ استراحات في الظل، وراقب زميلك.",
        "استرح في الظل أكثر، وخفّف العمل الشاق، واشرب الماء كل 15 دقيقة، والتزم بجدول الراحة الذي يحدده المشرف.",
        "أوقف العمل الشاق غير الضروري الآن. انتقل إلى الظل واشرب الماء، ولا تواصل إلا المهام الضرورية مع فترات راحة صارمة.",
    ],
    "hi": [
        "नियमित रूप से पानी पीते रहें और गर्मी से होने वाली बीमारी के लक्षण पहचानें।",
        "हर 15–20 मिनट में एक कप पानी पिएँ, छाँव में ब्रेक लें, और अपने साथी का ध्यान रखें।",
        "छाँव में ज़्यादा आराम करें, भारी काम कम करें, हर 15 मिनट पानी पिएँ, और सुपरवाइज़र के ब्रेक शेड्यूल का पालन करें।",
        "गैर-ज़रूरी भारी काम अभी रोकें। छाँव में जाएँ, पानी पिएँ, और सिर्फ़ ज़रूरी काम सख़्त आराम के साथ करें।",
    ],
}

T = {
    "alert": {
        "en": "HeatGuard: {level} heat risk at {site}. Feels like {c}°C.\n{action}",
        "ur": "ہیٹ گارڈ: {site} پر گرمی کا خطرہ — {level}۔ محسوس ہونے والا درجہ حرارت {c}°C۔\n{action}",
        "ar": "HeatGuard: خطر الحرارة في {site} — {level}. الحرارة المحسوسة {c}°م.\n{action}",
        "hi": "हीटगार्ड: {site} पर गर्मी का ख़तरा — {level}। महसूस तापमान {c}°C।\n{action}",
    },
    "ask_ok": {
        "en": "Are you OK? Tap a button.",
        "ur": "کیا آپ ٹھیک ہیں؟ بٹن دبائیں۔",
        "ar": "هل أنت بخير؟ اضغط على أحد الأزرار.",
        "hi": "क्या आप ठीक हैं? बटन दबाएँ।",
    },
    "btn_ok": {"en": "I'm OK", "ur": "میں ٹھیک ہوں", "ar": "أنا بخير", "hi": "मैं ठीक हूँ"},
    "btn_unwell": {"en": "Feeling unwell", "ur": "طبیعت خراب ہے", "ar": "أشعر بتعب", "hi": "तबीयत ठीक नहीं"},
    "thanks_ok": {
        "en": "Thank you. Keep drinking water and take your breaks.",
        "ur": "شکریہ۔ پانی پیتے رہیں اور وقفے لیتے رہیں۔",
        "ar": "شكرًا. واصل شرب الماء وخذ فترات الراحة.",
        "hi": "धन्यवाद। पानी पीते रहें और ब्रेक लेते रहें।",
    },
    "unwell_reply": {
        "en": "Help is coming: your supervisor and first-aider have been told. Move to shade now, sip cool water, and loosen tight clothing. If you feel confused, faint, or stop sweating, call {emergency} now.",
        "ur": "مدد آ رہی ہے: آپ کے سپروائزر اور فرسٹ ایڈ والے کو اطلاع دے دی گئی ہے۔ ابھی سائے میں جائیں، ٹھنڈا پانی گھونٹ گھونٹ پیئیں، اور تنگ کپڑے ڈھیلے کریں۔ اگر چکر آئیں، بے ہوشی محسوس ہو یا پسینہ آنا بند ہو جائے تو فوراً {emergency} پر کال کریں۔",
        "ar": "المساعدة في الطريق: تم إبلاغ مشرفك ومسؤول الإسعافات الأولية. انتقل إلى الظل الآن، واشرب ماءً باردًا ببطء، وفكّ الملابس الضيقة. إذا شعرت بالارتباك أو الإغماء أو توقف التعرق، اتصل بالرقم {emergency} فورًا.",
        "hi": "मदद आ रही है: आपके सुपरवाइज़र और फ़र्स्ट-एड वाले को बता दिया गया है। अभी छाँव में जाएँ, ठंडा पानी घूँट-घूँट पिएँ, और तंग कपड़े ढीले करें। अगर उलझन, बेहोशी लगे या पसीना आना बंद हो जाए, तो तुरंत {emergency} पर कॉल करें।",
    },
    "consent_request": {
        "en": "HeatGuard heat-safety alerts for {company}. We send heat warnings and ask if you're OK during hot hours. We keep only your phone number, crew and replies, and delete replies after 30 days. Your replies are never used for discipline, pay or hiring. Reply YES to join, or STOP to leave at any time.",
        "ur": "{company} کے لیے ہیٹ گارڈ گرمی سے حفاظت کے الرٹ۔ ہم گرم اوقات میں گرمی کی وارننگ بھیجتے ہیں اور پوچھتے ہیں کہ آپ ٹھیک ہیں۔ ہم صرف آپ کا فون نمبر، ٹیم اور جوابات رکھتے ہیں، اور جوابات 30 دن بعد مٹا دیتے ہیں۔ آپ کے جوابات کبھی سزا، تنخواہ یا بھرتی کے لیے استعمال نہیں ہوتے۔ شامل ہونے کے لیے YES اور کسی بھی وقت چھوڑنے کے لیے STOP لکھیں۔",
        "ar": "تنبيهات HeatGuard للسلامة من الحرارة لدى {company}. نرسل تحذيرات الحرارة ونسألك إن كنت بخير خلال الساعات الحارة. نحتفظ فقط برقم هاتفك وفريقك وردودك، ونحذف الردود بعد 30 يومًا. لا تُستخدم ردودك أبدًا في التأديب أو الأجر أو التوظيف. أرسل YES للانضمام، أو STOP للمغادرة في أي وقت.",
        "hi": "{company} के लिए हीटगार्ड गर्मी-सुरक्षा अलर्ट। हम गर्म घंटों में गर्मी की चेतावनी भेजते हैं और पूछते हैं कि आप ठीक हैं या नहीं। हम सिर्फ़ आपका फ़ोन नंबर, टीम और जवाब रखते हैं, और जवाब 30 दिन बाद मिटा देते हैं। आपके जवाब कभी सज़ा, वेतन या भर्ती के लिए इस्तेमाल नहीं होते। जुड़ने के लिए YES लिखें, या कभी भी छोड़ने के लिए STOP लिखें।",
    },
    "consent_yes": {
        "en": "You're in. You'll get heat alerts for your crew. Reply STOP at any time to leave.",
        "ur": "آپ شامل ہو گئے۔ آپ کو اپنی ٹیم کے لیے گرمی کے الرٹ ملیں گے۔ چھوڑنے کے لیے کسی بھی وقت STOP لکھیں۔",
        "ar": "تم تسجيلك. ستصلك تنبيهات الحرارة لفريقك. أرسل STOP في أي وقت للمغادرة.",
        "hi": "आप जुड़ गए। आपको अपनी टीम के लिए गर्मी के अलर्ट मिलेंगे। छोड़ने के लिए कभी भी STOP लिखें।",
    },
    "consent_stop": {
        "en": "You've left HeatGuard. You won't get more messages. Reply YES to rejoin.",
        "ur": "آپ نے ہیٹ گارڈ چھوڑ دیا ہے۔ آپ کو مزید پیغامات نہیں ملیں گے۔ دوبارہ شامل ہونے کے لیے YES لکھیں۔",
        "ar": "لقد غادرت HeatGuard. لن تصلك رسائل أخرى. أرسل YES للعودة.",
        "hi": "आपने हीटगार्ड छोड़ दिया है। अब आपको संदेश नहीं मिलेंगे। फिर से जुड़ने के लिए YES लिखें।",
    },
    "sup_warning": {
        "en": "HeatGuard outlook: {crew} at {site} will reach {level} around {time} (in about {mins} min). Plan now: move heavy tasks earlier, schedule shade breaks, and prepare water and cooling.",
        "ur": "ہیٹ گارڈ پیشگوئی: {site} پر {crew} تقریباً {time} بجے ({mins} منٹ میں) {level} تک پہنچ جائے گی۔ ابھی منصوبہ بنائیں: بھاری کام پہلے کروائیں، سائے میں وقفے طے کریں، اور پانی اور ٹھنڈک کا انتظام کریں۔",
        "ar": "توقعات HeatGuard: سيصل {crew} في {site} إلى مستوى {level} حوالي {time} (بعد نحو {mins} دقيقة). خطّط الآن: قدّم المهام الشاقة، وحدّد استراحات في الظل، وجهّز الماء ووسائل التبريد.",
        "hi": "हीटगार्ड पूर्वानुमान: {site} पर {crew} लगभग {time} बजे ({mins} मिनट में) {level} स्तर पर पहुँचेगी। अभी योजना बनाएँ: भारी काम पहले करवाएँ, छाँव में ब्रेक तय करें, और पानी व ठंडक का इंतज़ाम करें।",
    },
    "sup_alert": {
        "en": "HeatGuard: {crew} at {site} is now at {level} (feels like {c}°C). Why: {why}. Action: {action}",
        "ur": "ہیٹ گارڈ: {site} پر {crew} اب {level} پر ہے (محسوس درجہ حرارت {c}°C)۔ وجہ: {why}۔ اقدام: {action}",
        "ar": "HeatGuard: {crew} في {site} الآن عند مستوى {level} (الحرارة المحسوسة {c}°م). السبب: {why}. الإجراء: {action}",
        "hi": "हीटगार्ड: {site} पर {crew} अब {level} स्तर पर है (महसूस तापमान {c}°C)। कारण: {why}। कदम: {action}",
    },
    "esc_unwell": {
        "en": "⚠️ HeatGuard escalation: {name} ({crew}, {site}) reported feeling unwell at {time}. Go to them now: move to shade, cool with water, give water if alert. Call {emergency} if confused, collapsed or not sweating. Reply ACK when you are with them.",
        "ur": "⚠️ ہیٹ گارڈ ہنگامی اطلاع: {name} ({crew}، {site}) نے {time} بجے طبیعت خراب ہونے کی اطلاع دی۔ ابھی ان کے پاس جائیں: سائے میں لے جائیں، پانی سے ٹھنڈا کریں، ہوش میں ہوں تو پانی پلائیں۔ الجھن، بے ہوشی یا پسینہ بند ہو تو {emergency} پر کال کریں۔ ان کے پاس پہنچ کر ACK لکھیں۔",
        "ar": "⚠️ تصعيد HeatGuard: أبلغ {name} ({crew}، {site}) عن شعوره بالتعب الساعة {time}. اذهب إليه الآن: انقله إلى الظل، وبرّده بالماء، وأعطه الماء إن كان واعيًا. اتصل بالرقم {emergency} إذا كان مرتبكًا أو فقد الوعي أو توقف تعرقه. أرسل ACK عندما تصل إليه.",
        "hi": "⚠️ हीटगार्ड आपात सूचना: {name} ({crew}, {site}) ने {time} बजे तबीयत ख़राब होने की सूचना दी। अभी उनके पास जाएँ: छाँव में ले जाएँ, पानी से ठंडा करें, होश में हों तो पानी दें। उलझन, बेहोशी या पसीना बंद हो तो {emergency} पर कॉल करें। उनके पास पहुँचकर ACK लिखें।",
    },
    "esc_no_reply": {
        "en": "⚠️ HeatGuard: {name} ({crew}, {site}) hasn't answered a {level} heat check-in for {mins} min. Please check on them now and reply ACK.",
        "ur": "⚠️ ہیٹ گارڈ: {name} ({crew}، {site}) نے {mins} منٹ سے {level} گرمی کے چیک اِن کا جواب نہیں دیا۔ براہِ کرم ابھی ان کی خیریت معلوم کریں اور ACK لکھیں۔",
        "ar": "⚠️ HeatGuard: لم يرد {name} ({crew}، {site}) على فحص الحرارة بمستوى {level} منذ {mins} دقيقة. يرجى الاطمئنان عليه الآن وإرسال ACK.",
        "hi": "⚠️ हीटगार्ड: {name} ({crew}, {site}) ने {mins} मिनट से {level} गर्मी चेक-इन का जवाब नहीं दिया। कृपया अभी उनका हाल पता करें और ACK लिखें।",
    },
    "ack_thanks": {
        "en": "Thanks: escalation marked as handled at {time}.",
        "ur": "شکریہ: ہنگامی اطلاع {time} بجے نمٹا دی گئی کے طور پر درج ہو گئی۔",
        "ar": "شكرًا: تم تسجيل التصعيد كمعالَج الساعة {time}.",
        "hi": "धन्यवाद: आपात सूचना {time} बजे निपटाई गई के रूप में दर्ज हो गई।",
    },
}

EMERGENCY = {"AE": "998", "PK": "1122 or 115"}


def t(key: str, lang: str, **kw) -> str:
    table = T[key]
    return table.get(lang, table["en"]).format(**kw)


def level_name(level: int, lang: str) -> str:
    return LEVEL_NAMES.get(lang, LEVEL_NAMES["en"])[level]


def action(level: int, lang: str) -> str:
    return ACTIONS.get(lang, ACTIONS["en"])[level]
