# Graph Report - /Users/admin/Documents/Razarabotka/BaDzi_bot  (2026-05-05)

## Corpus Check
- 59 files · ~71,359 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 772 nodes · 1335 edges · 45 communities detected
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 284 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]

## God Nodes (most connected - your core abstractions)
1. `Pillar` - 113 edges
2. `_mk()` - 81 edges
3. `_mk()` - 36 edges
4. `ChartInput` - 34 edges
5. `_names_zh()` - 33 edges
6. `_b()` - 27 edges
7. `_mk()` - 24 edges
8. `_s()` - 22 edges
9. `SymbolicStar` - 21 edges
10. `StructuresOutput` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Pillar` --uses--> `Hidden stems (藏干) tests -- all 12 branches x 3 schools.`  [INFERRED]
  calculator/models.py → tests/unit/test_calculator/test_hidden_stems.py
- `Pillar` --uses--> `Tests for calculator/interactions.py — branch/stem interactions (合沖刑害破).`  [INFERRED]
  calculator/models.py → tests/unit/test_calculator/test_interactions.py
- `Pillar` --uses--> `Build 4 pillars from a list of (stem, branch) tuples in order Y/M/D/H.`  [INFERRED]
  calculator/models.py → tests/unit/test_calculator/test_interactions.py
- `Pillar` --uses--> `Day Master strength and useful/harmful god tests.`  [INFERRED]
  calculator/models.py → tests/unit/test_calculator/test_day_master.py
- `Pillar` --uses--> `Ten Gods (十神) mapping tests.`  [INFERRED]
  calculator/models.py → tests/unit/test_calculator/test_ten_gods.py

## Hyperedges (group relationships)
- **Калькулятор Бацзы — компоненты** — four_pillars, ten_gods, day_master, hidden_stems, interactions, luck_pillars, symbolic_stars, ming_gong, tai_yuan, qi_phases [EXTRACTED 1.00]
- **Мульти-модельный AI** — claude_sonnet, qwen_36, kimi_moonshot [EXTRACTED 1.00]
- **AI Pipeline** — ai_router, ai_orchestrator, ai_synthesis, ai_fallback [EXTRACTED 1.00]
- **Хронобиологический модуль** — true_solar_time, equation_of_time, geocoding, tz_database, dst_history [EXTRACTED 1.00]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (14): _mk(), _names(), TestDayStemAnchored, TestGouJiao, TestKongWang, TestMonthBranchAnchored, TestMonthBranchToStem, TestRealChart (+6 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (70): calculate_auxiliary_pillars(), calculate_ming_gong(), calculate_tai_yuan(), Auxiliary pillars 胎元 (Tai Yuan, Conception Pillar) and 命宫 (Ming Gong, Life Palac, Stem of 寅 month for the given year stem (五虎遁年起月)., Conception pillar (胎元) = month + (1 stem, 3 branches)., Life Palace (命宫) by 中州派 reflection rule., Compute 胎元 and 命宫 from the four main pillars. (+62 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (37): calculate_luck_pillars(), _decompose_age(), _is_forward(), _nearest_jie_jd(), _pillar_60_idx(), Luck Pillars (大運) generation for a Ba Zi chart.  Direction rule:   Yang year + m, Return 8 Luck Pillars (大運) with minute-level precision, or None if no gender., Find unique 60-cycle index for (stem_idx, branch_idx). (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (56): Фолбэк-механизм, AI Orchestrator (мульти-модельный), Семантический маршрутизатор, Синтез ответов, Telegram Bot (aiogram 3.x), AI-консультант Анастасия, BaseMiddleware, BaseSettings (+48 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (10): _mk(), _names_zh(), TestCascadePriority, TestFollowing, TestMonoelement, TestMonthSpecial, TestOutputIntegrity, TestRegularStructures (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (7): Day Master strength and useful/harmful god tests., TestDmElement, TestDmStrengthScore, TestElementBalance, TestIsStrongDm, TestSeasonalState, TestYongShenJiShen

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (8): _b(), Hidden stems (藏干) tests -- all 12 branches x 3 schools., TestChartHiddenStems, TestCrossSchool, TestKenLai, TestModern, TestReturnTypes, TestTraditional

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (6): Ten Gods (十神) mapping tests., _s(), TestAllPairsValid, TestChartTenGods, TestTenGodsFromDing, TestTenGodsFromJia

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (13): _mk(), Tests for calculator/interactions.py — branch/stem interactions (合沖刑害破)., Build 4 pillars from a list of (stem, branch) tuples in order Y/M/D/H., TestBranchClashes, TestHalfHarmonies, TestHarmsAndBreaks, TestNoInteractions, TestPillarTracking (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (15): Base, Base, ChartRepository, ConsultationRepository, DeclarativeBase, Chart, Consultation, Event (+7 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (6): Four Pillars generation tests.  Reference charts (user-verified against professi, TestEarlyLatRat, TestFourPillarsNovokuznetsk1997, TestFourPillarsVolzhsky1999, TestMonthBoundary, TestYearBoundary

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (6): _mk(), _p(), TestAuxiliaryPillars, TestCycleProperties, TestMingGong, TestTaiYuan

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (4): Solar terms (24 Jie Qi) calculation tests., TestSolarTermDatetime, TestSolarTermJd, TestSolarTermNames

### Community 13 - "Community 13"
Cohesion: 0.13
Nodes (5): _make(), TestChartInput, TestChartOutput, TestPillar, TestStemBranchConstants

### Community 14 - "Community 14"
Cohesion: 0.14
Nodes (15): dm_element(), dm_strength_score(), element_balance(), is_strong_dm(), ji_shen(), Day Master (日主) strength, element balance, and useful/harmful gods., Percentage of each element in the chart (values sum to 1.0).      Heavenly stems, Numeric DM strength score. Positive = strong (旺), negative = weak (弱).      Comb (+7 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (4): Swiss Ephemeris wrapper tests.  Astronomical reference points (UTC):   Summer so, TestJulianDay, TestSetEphemerisPath, TestSunLongitude

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (3): True Solar Time calculation tests.  Reference EoT values (Jean Meeus / NOAA):, TestEquationOfTime, TestTrueSolarTime

### Community 17 - "Community 17"
Cohesion: 0.25
Nodes (10): _approx_jd(), _find_solar_term_jd(), _jd_to_utc(), 24 Solar Terms (Jie Qi, 节气) calculation via Newton-Raphson search., UTC datetime of solar term `term_index` in Gregorian year `year`., Rough JD for term `term_index` in Gregorian year `year`., Newton-Raphson refinement until sun longitude equals target_lon., JD when sun longitude equals term_index * 15° in Gregorian year `year`.      Arg (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.25
Nodes (7): julian_day(), Swiss Ephemeris wrapper — thin facade over pyswisseph., Point pyswisseph at JPL DE431 files.  Falls back to Moshier if path missing., Convert a UTC-aware datetime to Julian Day Number (UT1)., Return ecliptic longitude of the Sun in degrees [0, 360)., set_ephemeris_path(), sun_longitude()

### Community 19 - "Community 19"
Cohesion: 0.4
Nodes (5): chart_ten_gods(), Ten Gods (十神) mapping for Ba Zi charts., Return the Ten God label of *target* relative to *day_master*., For each pillar return [stem_god, *hidden_gods].      The day pillar's heavenly, ten_god()

### Community 20 - "Community 20"
Cohesion: 0.4
Nodes (5): equation_of_time(), True Solar Time (TST) calculation.  TST = LMT + EoT   LMT  — Local Mean Time: UT, Return Equation of Time in minutes (Apparent Solar Time - Local Mean Time)., Convert UTC datetime to True Solar Time (naive) at the given longitude.      Arg, true_solar_time()

### Community 21 - "Community 21"
Cohesion: 0.4
Nodes (5): chart_hidden_stems(), hidden_stems(), Hidden stems (藏干) — Heavenly Stems concealed inside each Earthly Branch.  Three, Return the hidden stems for *branch* under the given *school*.      The list is, Map each pillar's branch to its hidden stems under *school*.      Returns a dict

### Community 22 - "Community 22"
Cohesion: 0.5
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 0.67
Nodes (3): call_perplexity_deep(), main(), Single deep-research call with detailed error logging.

### Community 24 - "Community 24"
Cohesion: 0.83
Nodes (3): get_engine(), get_session_factory(), session_scope()

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (2): _import_graphify(), main()

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): create_initial_tables  Revision ID: 151398db4f39 Revises: Create Date: 2026-05-0

## Knowledge Gaps
- **33 isolated node(s):** `Symbolic Stars (神煞) reference tables.  All tables are sourced from the canonical`, `24 Solar Terms (Jie Qi, 节气) calculation via Newton-Raphson search.`, `Rough JD for term `term_index` in Gregorian year `year`.`, `Newton-Raphson refinement until sun longitude equals target_lon.`, `JD when sun longitude equals term_index * 15° in Gregorian year `year`.      Arg` (+28 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 26`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `create_initial_tables  Revision ID: 151398db4f39 Revises: Create Date: 2026-05-0`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Pillar` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 11`, `Community 13`, `Community 14`, `Community 19`?**
  _High betweenness centrality (0.436) - this node is a cross-community bridge._
- **Why does `ChartInput` connect `Community 2` to `Community 1`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `TestDayStemAnchored` connect `Community 0` to `Community 1`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 111 inferred relationships involving `Pillar` (e.g. with `Symbolic Stars (神煞) detection for a Ba Zi chart.  Detects 63 classical stars via` and `Find unique 60-cycle index x with x%10=stem_idx and x%12=branch_idx.`) actually correct?**
  _`Pillar` has 111 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `ChartInput` (e.g. with `Luck Pillars (大運) generation for a Ba Zi chart.  Direction rule:   Yang year + m` and `Find unique 60-cycle index for (stem_idx, branch_idx).`) actually correct?**
  _`ChartInput` has 32 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Symbolic Stars (神煞) reference tables.  All tables are sourced from the canonical`, `24 Solar Terms (Jie Qi, 节气) calculation via Newton-Raphson search.`, `Rough JD for term `term_index` in Gregorian year `year`.` to the rest of the system?**
  _33 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._