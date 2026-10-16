"""Self-check ar_shape against arabic_reshaper + python-bidi on plain strings, plus token cases."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import arabic_reshaper
from bidi import get_display

from ar_shape import to_visual

ref_cfg = arabic_reshaper.ArabicReshaper(configuration={"delete_harakat": False, "support_ligatures": True,
                                                        "ARABIC LIGATURE ALLAH": False, "ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM": False})

PLAIN = [
    "لعبة جديدة",
    "الإعدادات",
    "هل تريد إغلاق اللعبة بالكامل؟",
    "لا شكرا",
    "استعد 35 نقطة صحة.",
    "زيادة إجمالية بنسبة 25%",
    "مستوى 5",
    "سلاح C.A.R.T. جديد",
    "إلى اللقاء، أيها الأصدقاء!",
    "ابحث عن نقطة الاستخراج التالية",
    "لأن الإله الآن",
]
fails = 0
for s in PLAIN:
    mine = to_visual(s, gap_em=0, adv_fix=0)
    ref = get_display(ref_cfg.reshape(s), base_dir="R")
    ok = mine == ref
    fails += not ok
    print(("OK  " if ok else "DIFF"), s, "|", mine, "|", ref if not ok else "")

TOKENS = [
    "اضغط مطولًا لإعادة السحب ({cost})",
    "استخدم [move] للتحرك.",
    "املأ <b><u>نقاط الاستخراج</u></b> بالأشياء الثمينة.",
    "صديقك صاحب أفضل حاسوب\\nيجب أن يستضيف.\\n\\nهل أنت هذا الصديق؟",
    "ها ها نعم!  :)",
    "{ping} مللي ثانية",
    "اللاعبون: {players:list:{}|،   |   ،   }",
]
for s in TOKENS:
    print("TOK ", s, "|", to_visual(s))
print("fails:", fails)
