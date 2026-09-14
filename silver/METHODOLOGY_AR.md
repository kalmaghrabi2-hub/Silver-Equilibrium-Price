# منهجية Silver Equilibrium Price

## الهدف
حساب سعر متعادل هيكلي للفضة `P*` يتم تحديثه آليًا يوميًا، مع الفصل بوضوح بين سعر السوق، القيمة الأسبوعية المرتبطة بعوامل السوق الكلية، وطبقة توازن العرض والطلب المادي. لا تُعرض النتيجة كحقيقة يقينية؛ بل كقيمة نموذجية قابلة للتدقيق مع حالة حوكمة واضحة.

## لماذا تختلف الفضة عن الذهب؟
الفضة أصل نقدي/استثماري وفي الوقت نفسه معدن صناعي مهم. لذلك لا يكفي نموذج يشبه الذهب فقط، ولا يكفي أيضًا الاعتماد على العرض والطلب الصناعي وحده. النموذج يستخدم طبقتين مكملتين:

1. طبقة أسبوعية تلتقط المحركات المالية والسوقية.
2. طبقة توازن مادي سنوية تلتقط ضغط العرض والطلب الفعلي.

## 1) Market Layer
السعر السوقي المرجعي الأساسي هو COMEX Silver Futures `SI=F` من Yahoo Finance Chart API، لأنه متاح آليًا بدون مفتاح مدفوع ويمكن الاحتفاظ بتاريخ طويل للمعايرة. يوجد fallback معلن إلى XAG من Gold API إذا تعطلت تغذية Yahoo.

لا يتم إخفاء نوع المصدر: الموقع يوضح ما إذا كانت القيمة Futures benchmark أو fallback spot feed.

## 2) Weekly ARX Fair Value
يتم تقدير سعر أسبوع واحد للأمام باستخدام نموذج Ridge ARX على لوغاريتم سعر الفضة، مع متغيرات متاحة عند الزمن t فقط:

- `LAG_SILVER_LOG`: لوغاريتم سعر الفضة السابق.
- `GC=F`: الذهب، لالتقاط العامل النقدي/الثمين المشترك.
- `DX-Y.NYB`: مؤشر الدولار الأمريكي.
- `^TNX`: عائد سندات الخزانة الأمريكية 10 سنوات.
- `^VIX`: تقلبات السوق/الطلب الدفاعي.
- `HG=F`: النحاس، كإشارة صناعية دورية مكملة لطبيعة الفضة الصناعية.

لا يتم استخدام بيانات مستقبلية، ولا interpolation أو imputation للمتغيرات الحرجة. يتم استخدام complete-case فقط.

### Walk-forward
- تدريب أولي: 156 أسبوعًا على الأقل.
- الاختبار: expanding one-step-ahead walk-forward.
- الحد الأدنى خارج العينة: 260 أسبوعًا.
- بوابة النجاح المحددة مسبقًا: `R² >= 0.60` و`MAPE <= 15%`.
- يتم حفظ معاملات النموذج ومقاييس الاختبار في `docs/silver/data/weekly_calibration.json`.

## 3) Physical Equilibrium Overlay
يستخدم أحدث جدول رسمي متحقق منه من World Silver Survey 2026 الصادر عن The Silver Institute والمنتج بواسطة Metals Focus.

المدخلات الحالية المنشورة:

### 2025 Actual
- Total Supply: 1,090.4 Moz
- Total Demand: 1,130.6 Moz
- Market Balance: -40.3 Moz
- Mine Production: 846.6 Moz
- Recycling: 197.6 Moz
- Industrial Demand: 657.4 Moz
- Coin & Net Bar Demand: 217.7 Moz
- Net Investment in ETPs: 278.1 Moz
- London annual average silver price: 40.03 USD/oz

### 2026 Forecast
- Total Supply: 1,066.4 Moz
- Total Demand: 1,112.6 Moz
- Market Balance: -46.3 Moz
- Mine Production: 844.1 Moz
- Recycling: 211.3 Moz
- Industrial Demand: 639.6 Moz
- Coin & Net Bar Demand: 257.6 Moz
- Net Investment in ETPs: 30.0 Moz

المصدر الأساسي: World Silver Survey 2026، جدول `Silver Supply and Demand`.

## 4) معادلة التوازن المادي
نستخدم الصيغة الهيكلية نفسها التي تربط اختلال الكمية بالسعر المطلوب لإعادة التوازن:

`Physical Multiplier = (D / S) ^ (1 / (εs - εd))`

حيث:

- `D`: إجمالي الطلب المتوقع/المتحقق.
- `S`: إجمالي العرض المتوقع/المتحقق.
- `εs = +0.36`.
- `εd = -0.40`.

قيم المرونة مأخوذة من تقديرات U.S. Geological Survey المنشورة في 2025 للفضة. تقرير USGS يوضح أن القيم المستخدمة للفضة هي Price Elasticity of Supply = `0.36` وPrice Elasticity of Demand = `-0.40`، مع الإشارة إلى أنها مبنية على static panel framework.

بالتالي:

`1 / (εs - εd) = 1 / 0.76 ≈ 1.31578947`

طبقة العرض والطلب لا تُعامل كقياس يومي؛ هي عامل هيكلي يتغير عندما تتغير البيانات الرسمية. يتم استخدام أحدث سنة/توقع رسمي مناسب للسنة الجارية.

## 5) السعر المتعادل المركب

`P*raw = Weekly Fair Value × Physical Multiplier`

ثم يطبق guardrail واسع فقط لمنع ناتج شاذ عند حدوث خلل في مصدر أو معامل:

`P* = clip(P*raw, 0.50 × Market Price, 1.60 × Market Price)`

وجود guardrail لا يحول نتيجة غير صالحة إلى نتيجة صالحة؛ إذا تم تفعيله يظهر ذلك صراحة على الموقع.

## 6) الحوكمة وحالة النموذج

### Weekly Gate
يصبح `PASS` فقط إذا اجتاز النموذج الاختبار خارج العينة المحدد مسبقًا.

### Physical Source Gate
يصبح `PASS` إذا كانت بيانات العرض والطلب من مصدر رسمي معروف، والسنة المستخدمة مناسبة، والحقول الأساسية مكتملة، والمرونات موثقة بمصدر خارجي.

### Composite Status
- `VALID`: Weekly Gate = PASS وPhysical Source Gate = PASS ولا توجد أخطاء حرجة.
- `PROVISIONAL`: البيانات متاحة لكن إحدى بوابات الحوكمة غير مكتملة أو توجد ملاحظة منهجية.
- `UNAVAILABLE`: لا يمكن حساب P* بسبب فقدان مدخل حرج.

## 7) التحديث الآلي
المستودع الإنتاجي المستقل هو:

`kalmaghrabi2-hub/Silver-Equilibrium-Price`

GitHub Actions يعمل يوميًا ويقوم بالآتي:

1. تنزيل التاريخ الأسبوعي العام للفضة والمتغيرات المالية.
2. إعادة معايرة Weekly ARX بالكامل.
3. تنفيذ walk-forward gate.
4. جلب أحدث سعر سوقي والمتغيرات اليومية.
5. قراءة أحدث fundamentals snapshot رسمي متحقق منه.
6. حساب Physical Multiplier.
7. حساب `P*` والانحراف بين السوق والسعر المتعادل.
8. تحديث `docs/silver/data/latest.json`.
9. Commit آلي للنتائج الجديدة إلى المستودع.

## 8) سياسة البيانات
- لا يتم اختلاق أي قيمة حرجة مفقودة.
- لا يتم backfill باستخدام قيمة مستقبلية.
- لا يتم تغيير بوابات النجاح بعد رؤية النتائج بغرض تمرير النموذج.
- بيانات World Silver Survey المستخدمة في الحساب تحفظ كـ snapshot مختصر للقيم اللازمة فقط مع المصدر والسنة، ولا يُعاد نشر التقرير الكامل.
- عند ظهور إصدار رسمي أحدث، يجب أن يحل محل snapshot الحالي بعد التحقق الآلي/اليدوي من الحقول الرئيسية.

## المصادر الأساسية
- The Silver Institute / Metals Focus — World Silver Survey 2026.
- U.S. Geological Survey — 2025 estimates of price elasticities for non-fuel minerals; silver PES `0.36`, PED `-0.40`.
- Yahoo Finance Chart API — `SI=F`, `GC=F`, `DX-Y.NYB`, `^TNX`, `^VIX`, `HG=F`.
- Gold API — XAG fallback only.
