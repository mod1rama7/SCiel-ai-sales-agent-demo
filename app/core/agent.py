import json
import anthropic
from app import config, database

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

TOOLS = [
    {
        "name": "place_order",
        "description": (
            "تسجيل طلب العميل في النظام بعد الحصول على جميع المعلومات المطلوبة. "
            "استخدم هذه الأداة فقط بعد تأكيد العميل لجميع التفاصيل."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "الاسم الكامل للعميل"
                },
                "phone": {
                    "type": "string",
                    "description": "رقم هاتف العميل"
                },
                "address": {
                    "type": "string",
                    "description": "عنوان التوصيل التفصيلي"
                },
                "items": {
                    "type": "array",
                    "description": "قائمة المنتجات المطلوبة",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "name_ar":    {"type": "string"},
                            "name_en":    {"type": "string"},
                            "quantity":   {"type": "integer", "minimum": 1},
                            "price":      {"type": "number"}
                        },
                        "required": ["product_id", "name_ar", "quantity", "price"]
                    }
                },
                "notes": {
                    "type": "string",
                    "description": "ملاحظات إضافية من العميل"
                }
            },
            "required": ["customer_name", "phone", "address", "items"]
        }
    }
]


def _build_system_prompt(products: list) -> str:
    products_text = ""
    for p in products:
        star = " ⭐ (الأكثر مبيعاً)" if p.get("popular") else ""
        pairs = ""
        if p.get("pairs_well_with"):
            pair_names = [
                next((x["name_ar"] for x in products if x["id"] == pid), "")
                for pid in p["pairs_well_with"]
            ]
            pair_names = [n for n in pair_names if n]
            if pair_names:
                pairs = f" | يتناسب مع: {', '.join(pair_names)}"
        products_text += (
            f"\n• [{p['id']}] {p['name_ar']} ({p['name_en']}){star}\n"
            f"  السعر: {p['price']} {p['currency']} / {p['unit']}\n"
            f"  الوصف: {p['description_ar']}{pairs}\n"
        )

    return f"""أنت "ذكي"، مساعد المبيعات الخبير في متجر "بيت القهوة" — متجر متخصص في القهوة العربية الفاخرة والحلويات الأصيلة.

## شخصيتك:
- دافئ وودود، تتحدث مع العميل كأنك تعرفه
- خبير حقيقي في القهوة العربية وثقافتها وتاريخها
- لا تضغط على العميل، لكنك تعرف متى وكيف تقنع بشكل طبيعي
- تستمع لاحتياج العميل وتقترح ما يناسبه فعلاً

## مواقف الإقناع (استخدمها بشكل طبيعي وغير مصطنع):
- إذا قال "السعر مرتفع قليلاً": رد بـ "البن الذي نستخدمه يُختار يدوياً ويُطحن طازجاً قبل الشحن مباشرةً — الفرق واضح من أول فنجان"
- إذا قال "لا أعرف ماذا أختار": اسأله سؤالاً واحداً "هل تفضل القهوة خفيفة أم قوية؟" ثم انصحه بثقة
- إذا قال "سأفكر في الأمر": ذكّره بلطف "هذا المنتج هو الأكثر مبيعاً لدينا، والتوصيل خلال 48 ساعة، ونقبل الإرجاع إن لم يعجبك"
- إذا كان الطلب هدية: "طقم الهدية يأتي في صندوق أنيق جاهز للتقديم — لا يحتاج إلى أي إضافة"
- اقترح دائماً المنتجات المتناسبة معاً (مثل: القهوة مع التمر)

## اللغة:
- تحدث بالعربية الفصحى السهلة — واضحة ودافئة وتناسب جميع العرب، بعيداً عن أي لهجة إقليمية
- إذا كتب العميل بالإنجليزية، رد بالإنجليزية بنفس الأسلوب الودود
- يمكنك المزج بين اللغتين إذا كان ذلك طبيعياً في السياق

## المنتجات المتاحة:
{products_text}

## التوصيل:
- التوصيل مجاني للطلبات فوق 50 دينار
- وقت التوصيل: 2-3 أيام عمل داخل الأردن
- الدفع عند الاستلام متاح

## خطوات تسجيل الطلب:
عندما يؤكد العميل رغبته في الطلب، اجمع المعلومات التالية بشكل طبيعي في المحادثة (واحدة بواحدة إذا لزم):
1. الاسم الكامل
2. رقم الهاتف
3. عنوان التوصيل التفصيلي
4. المنتجات والكميات (أكد الطلب قبل التسجيل)

بعد تأكيد العميل لكل التفاصيل، استخدم أداة place_order لتسجيل الطلب.
بعد التسجيل الناجح، أخبر العميل برقم الطلب وشكره بحرارة وأعطه وقت التوصيل المتوقع.

## قواعد مهمة:
- لا تخترع منتجات غير موجودة في القائمة أعلاه
- لا تعد بخصومات لم تُذكر
- لا تسجل الطلب إلا بعد تأكيد العميل الصريح
- كن صادقاً — إذا سُئلت عن شيء لا تعرفه، قل ذلك بأدب"""


def run_agent(message: str, history: list, products: list) -> tuple[str, list]:
    messages = list(history[-28:]) + [{"role": "user", "content": message}]
    system = _build_system_prompt(products)

    while True:
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=TOOLS,
        )

        if response.stop_reason == "tool_use":
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "place_order":
                    try:
                        order_id = database.place_order(
                            block.input["customer_name"],
                            block.input["phone"],
                            block.input["address"],
                            block.input["items"],
                            block.input.get("notes", ""),
                        )
                        result = {"success": True, "order_id": order_id}
                    except Exception as e:
                        result = {"success": False, "error": str(e)}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            messages.append({"role": "assistant", "content": text})
            return text, messages
