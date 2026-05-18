# Macro Matching Rules (Stage A2)

Stage A2 maps every Kalshi series in `outputs/kalshi_series_all.csv` (10,161 series)
to entries in `outputs/auto/macro_event_master_list.csv`. Match → series is
"macro Kalshi" for this plan; no match → out of scope (handled by later plans).

## Rules

1. **Case-insensitive regex** against the concatenation `title + " " + sub_title + " " + rules_primary (if any)`.
2. **Word boundaries** (`\b...\b`) — no substring matches inside other words.
3. Each event_name has a small alias set listed below. **All aliases are from
   official BLS / BEA / Census / Fed / UMich abbreviations**; none are guessed.
4. A Kalshi series can match **multiple** events (e.g., a "Recession" market may
   match both `gdp` and `recession_prob`).
5. Adding any new alias triggers a *full re-run* of Stage A2 (`scripts/auto/s_a2_kalshi_macro_match.py`).

## Alias dictionary

Each line: `event_name (from master list)` → list of patterns.

| event_name | aliases (official source) |
|---|---|
| nonfarm payrolls | `nonfarm payroll`, `\bnfp\b`, `payroll report`, `jobs report`, `\bpayrolls?\b` (BLS Employment Situation) |
| unemployment rate | `unemployment rate`, `\bu-?3\b`, `jobless rate` (BLS U-3) |
| initial jobless | `initial jobless`, `initial claims`, `weekly jobless` (DOL UI Claims) |
| continuing jobless | `continuing jobless`, `continued claims` (DOL) |
| jolts | `\bjolts\b`, `job openings`, `labor turnover` (BLS JOLTS) |
| adp employment | `\badp\b.*employ`, `adp national employment` (ADP) |
| nonfarm productivity | `nonfarm productivity`, `productivity and costs` (BLS) |
| participation rate | `participation rate`, `labor force participation` (BLS) |
| average hourly earnings | `average hourly earnings`, `\bahe\b`, `wage growth` (BLS) |
| cpi | `\bcpi\b`, `consumer price index`, `inflation rate` (BLS CPI) |
| core cpi | `core cpi`, `cpi ex food and energy`, `core inflation` (BLS) |
| ppi | `\bppi\b`, `producer price index`, `producer inflation` (BLS PPI) |
| pce | `\bpce\b`, `personal consumption expenditure`, `pce price index` (BEA) |
| core pce | `core pce`, `pce ex food and energy` (BEA) |
| retail sales | `retail sales`, `advance retail sales` (Census MARTS) |
| industrial production | `industrial production`, `\bip\b`, `indpro` (Fed G.17) |
| durable goods | `durable goods`, `durable goods orders` (Census M3) |
| factory orders | `factory orders`, `new manufacturers' orders` (Census M3) |
| construction spending | `construction spending`, `value of construction put in place` (Census C30) |
| housing starts | `housing starts`, `new residential construction` (Census) |
| building permits | `building permits`, `new privately-owned housing units authorized` (Census) |
| new home sales | `new home sales`, `new residential sales` (Census) |
| existing home sales | `existing home sales` (NAR — via Census aggregation) |
| case-shiller | `case-shiller`, `case shiller`, `s&p corelogic` (S&P/Case-Shiller) |
| consumer sentiment | `consumer sentiment`, `michigan sentiment`, `\bumich\b` (UMich Surveys) |
| michigan consumer | `michigan sentiment`, `michigan consumer`, `\bumich\b` |
| consumer confidence | `consumer confidence`, `cci\b`, `conference board confidence` (Conference Board) |
| import price | `import price`, `import price index` (BLS) |
| personal income | `personal income` (BEA) |
| personal spending | `personal spending`, `personal expenditure` (BEA) |
| trade balance | `trade balance`, `international trade in goods` (BEA/Census FT900) |
| ism manufacturing | `\bism manufacturing\b`, `ism mfg`, `\bpmi manufacturing\b` (ISM) |
| ism non-manufacturing | `\bism non-?manufacturing\b` (ISM) |
| ism services | `\bism services\b` (ISM) |
| manufacturing pmi | `manufacturing pmi`, `s&p global manufacturing pmi` (S&P Global) |
| services pmi | `services pmi`, `s&p global services pmi` (S&P Global) |
| gdp | `\bgdp\b`, `gross domestic product` (BEA) |
| fomc | `\bfomc\b`, `federal open market committee` (Fed) |
| fed interest rate | `fed interest rate`, `federal funds rate`, `fed funds rate`, `fed rate decision` (Fed) |
| fed chair | `fed chair`, `federal reserve chair` (Fed) |

FRED indicator names from the catalog also match via their canonical name OR
series_id (e.g., `PAYEMS`, `UNRATE`, `CPIAUCSL`).

## Negative controls (verified that rules don't false-positive these)

These Kalshi titles must *not* match any macro event:

- "Will the Beatles have 3.5B streams in 2026?" → no match (music)
- "MrBeast Million Dollar Puzzle completion" → no match
- "Will Elon Musk visit Mars in his lifetime?" → no match
- "Oscar for Best Picture" → no match
- "Boxing match result" → no match

If any of these match, the rules have a bug → fix and re-run.
