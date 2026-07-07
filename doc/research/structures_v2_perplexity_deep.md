# Bazi 格局 Research v2 — Perplexity sonar-deep-research

**Started:** 2026-05-05 15:25:29  
**Finished:** 2026-05-05 15:28:49  
**Duration:** 199.8s  
**Model:** perplexity/sonar-deep-research

---

# Comprehensive Deterministic Reference Guide to BaZi Structures (格局) for Computational Analysis

This report presents a systematic, machine-readable specification for detecting and classifying all major BaZi structures (格局) in the classical Ziping methodology, organized by deterministic priority and technical detection rules suitable for implementation in a Python-based BaZi calculator framework. The guide synthesizes canonical classical texts—including the 三命通会 (San Ming Tong Hui), 渊海子平 (Yuan Hai Zi Ping), and 滴天髓 (Di Tian Sui)—into explicit algorithmic specifications for 30 major structures across six categorical hierarchies, with determinism ratings, break conditions, and priority detection sequences.

## Foundational Concepts for Deterministic Structure Detection

Before enumerating specific structures, the computational detection system must establish several foundational calculations that serve as prerequisites for all subsequent structure identification. These calculations operate on immutable field values derived from the Four Pillars chart: the Day Master (日主, represented as the Heavenly Stem of the Day Pillar), the four Heavenly Stems across all pillars, the four Earthly Branches across all pillars, and the hidden stems within each branch according to the classical canon. In the BaZi system, structure detection (格局判断) is fundamentally hierarchical and sequential; attempting to identify structures out of proper order produces systematic misclassification errors[1][12].

The canonical priority sequence for structure detection, as established in the Zi Ping Zhen Quan and reinforced across classical commentary, follows this hierarchical order: rare exotic structures (containing specific celestial stems or branch configurations like 魁罡) are evaluated first; transformation patterns (化气格) are checked second; following patterns (从格) third; monoelement specialized patterns (一气格) fourth; month-lord special patterns (建禄, 月刃) fifth; and finally the eight regular patterns (正格) form the baseline classification when no higher-priority structure is activated[50]. This ordering reflects classical tradition because rarer patterns operate under different logical systems than regular patterns, and misidentifying a following structure as a regular structure would produce fundamentally incorrect analysis.

The hidden stem configuration of each Earthly Branch forms the critical substrate upon which structure detection operates. According to the canonical classical texts, each of the twelve Earthly Branches contains either one, two, or three hidden Heavenly Stems arranged in a hierarchy of influence: the Main Qi (本气, representing approximately 60–70% of the branch's elemental influence), the Middle Qi (中气, typically 20–30%), and the Residual Qi (余气, the remaining 5–10%)[7][16][41]. The transparent revelation of these hidden stems into the surface Heavenly Stems through direct elemental correspondence is termed 透出 in classical texts, and this transparency is a prerequisite for most structure formations.

## The Eight Regular Structures (正格): Deterministic Detection Schema

The eight regular structures form the foundational classification system when no rare or specialized structures are activated. Each regular structure is defined by the relationship between the Day Master and the dominant hidden stem of the Month Branch (月支), revealed through a Heavenly Stem somewhere in the four pillars[1][50]. The detection process for each regular structure follows an identical algorithmic sequence: identify the hidden stems of the Month Branch in priority order (Main Qi first, Middle Qi second, Residual Qi third); find whether any of these hidden stems appears in the Heavenly Stems of any pillar; determine the Ten God relationship between that revealed stem and the Day Master; classify the resulting structure accordingly.

### Structure 1: 正官格 (Direct Officer Pattern) — High Determinism

The Direct Officer Pattern emerges when the Main Qi (本气) of the Month Branch is the Day Master's Direct Officer element, meaning the element that controls the Day Master with opposite Yin-Yang polarity[12]. For computational purposes, the Direct Officer relationship is defined by the Five Element control cycle (克) with opposite polarity: if the Day Master is Jia Wood (Yang), then Xin Metal (Yin) is its Direct Officer; if Yi Wood (Yin), then Geng Metal (Yang) is its Direct Officer. According to source materials, the detection sequence prioritizes whether this Direct Officer element appears in the Month Heavenly Stem first, the Year Heavenly Stem second, and the Hour Heavenly Stem third[50].

The structure is broken (破格) by several taboo conditions identified in classical texts[10]: when two Direct Officer stems appear simultaneously in the four pillars, creating ambiguity and weakening the pattern (this condition is called 官混 or "officer mixing"); when Robbery of Wealth (劫财) or Peer (比肩) elements appear without a corresponding Wealth element to redirect their energy, simultaneously weakening the Direct Officer's legitimacy and destabilizing the Day Master; when the Direct Officer element is severely controlled by strong metal-controlling elements without a Seal (印) to protect it. The useful god (用神) of a pure Direct Officer Pattern is typically the Officer element itself for strengthening authority and status, with secondary support from Wealth elements (which generate the Officer through the productive cycle) and Seal/Resource elements (which support the weakened Day Master against the Officer's pressure). The harmful god (忌神) is uniformly the Eating God and Hurting Officer elements, which directly attack the Officer's legitimacy.

### Structure 2: 七杀格 (Seven Killings Pattern) — High Determinism

The Seven Killings Pattern activates when the Main Qi (本气) of the Month Branch is the Day Master's Seven Killings element—the element that controls the Day Master with the same Yin-Yang polarity[12]. For Day Master Jia Wood (Yang), Geng Metal (Yang) is Seven Killings; for Yi Wood (Yin), Xin Metal (Yin) is Seven Killings. The computational detection mirrors the Direct Officer process: check Month Stem first, Year Stem second, Hour Stem third for the transparent revelation of the Seven Killings element.

Seven Killings patterns are notably fragile structures requiring protective mechanisms. The pattern is broken when either Eating God (食神) or Hurting Officer (伤官) elements appear prominently, as these output elements directly attack and neutralize the Seven Killings' controlling force[10][10]. The pattern is also broken when Peer or Rob Wealth elements overwhelm the chart without corresponding Wealth generation, as the Day Master then cannot stabilize under the Seven Killings' pressure. The useful god in a functional Seven Killings Pattern is the Seven Killings element itself for generating authority and executive power, along with Wealth elements (which generate the Seven Killings through the productive cycle) and potentially Seal/Resource elements (if the Day Master needs protection from excessive Killings pressure). The harmful god is uniformly the Eating God and Hurting Officer.

### Structure 3: 正财格 (Direct Wealth Pattern) — High Determinism

The Direct Wealth Pattern forms when the Main Qi (本气) of the Month Branch is the Day Master's Direct Wealth element—the Five Element that the Day Master controls with opposite Yin-Yang polarity[12]. For Jia Wood (Yang), Ji Earth (Yin) is Direct Wealth; for Yi Wood (Yin), Wu Earth (Yang) is Direct Wealth. Detection sequence: Month Stem, Year Stem, Hour Stem.

The Direct Wealth Pattern is broken by the appearance of strong Seal/Resource elements without corresponding Eating God to consume them, as Seals directly oppose and weaken Wealth. It is also broken by the presence of excessive Robbery or Peer elements that dissipate the Day Master's capacity to sustain Wealth accumulation without generating a corresponding Officer or Resource to balance them[10]. The useful god is primarily the Wealth element for generating income and material accumulation, secondarily the Eating God (which generates Wealth through the productive cycle), and the Direct Officer (which adds legitimacy and status to wealth). The harmful god is the Seal/Resource elements and any Robbery/Peer without Officer support.

### Structure 4: 偏财格 (Indirect Wealth Pattern) — High Determinism

The Indirect Wealth Pattern activates when the Main Qi (本气) of the Month Branch is the Day Master's Indirect Wealth element—the element the Day Master controls with the same Yin-Yang polarity[12][34]. For Jia Wood (Yang), Wu Earth (Yang) is Indirect Wealth; for Yi Wood (Yin), Ji Earth (Yin) is Indirect Wealth. Detection: Month Stem first, then Year Stem, then Hour Stem.

The Indirect Wealth Pattern breaks identically to the Direct Wealth Pattern: strong Seals without consumption, or excessive Robbery/Peer elements. However, Indirect Wealth structures tolerate slightly higher Robbery/Peer presence than Direct Wealth because Indirect Wealth's speculative nature creates different psychological dynamics—the chart holder with Indirect Wealth is more prone to risk-taking and less emotionally attached to money, thus tolerating competitive pressure differently[34]. The useful god is the Indirect Wealth element plus the Hurting Officer (which generates Indirect Wealth), and the Eating God provides secondary support. The harmful god is Seal/Resource elements and Robbery/Peer without Officer mediation.

### Structure 5: 正印格 (Direct Seal/Resource Pattern) — High Determinism

The Direct Seal Pattern emerges when the Main Qi (本气) of the Month Branch is the Day Master's Direct Resource element—the element that produces the Day Master with opposite Yin-Yang polarity[12]. For Jia Wood (Yang), Gui Water (Yin) is Direct Resource; for Yi Wood (Yin), Ren Water (Yang) is Direct Resource. Detection: Month Stem, Year Stem, Hour Stem.

Direct Resource Patterns break critically when Wealth elements appear prominently, creating the taboo condition 贪财坏印 ("greed for wealth ruins the seal") wherein the chart holder abandons education, stability, and noble support in pursuit of money, destroying the legitimate foundation of their success[10][10]. The pattern also breaks when the Day Master becomes excessively strong through too many Peer or Robbery elements, making Resource redundant and transforming it into a burden. The useful god is primarily the Direct Resource element for education, protection, and nurturing support; secondarily, Peer/Robbery elements stabilize the Day Master against excessive Officer pressure. The harmful god is uniformly the Wealth element.

### Structure 6: 偏印格 (Indirect Seal/Resource Pattern) — High Determinism

The Indirect Resource Pattern forms when the Main Qi (本气) of the Month Branch is the Day Master's Indirect Resource element—the element producing the Day Master with the same Yin-Yang polarity[12]. For Jia Wood (Yang), Ren Water (Yang) is Indirect Resource; for Yi Wood (Yin), Gui Water (Yin) is Indirect Resource. Detection: Month Stem, Year Stem, Hour Stem.

Indirect Resource patterns carry reputation in classical texts for harboring psychological complexity and potential self-sabotage[35]. The pattern breaks when Eating God elements (especially Eating God from the Day Master's productive cycle) appear and are controlled by the Indirect Resource, as this configuration produces the notorious 枭神夺食 ("the Owl God robs the eating god") taboo wherein the chart holder's creative output and children-related matters are blocked or turned into misfortune[12][10]. The pattern also breaks when Wealth elements overwhelm the chart. The useful god is the Indirect Resource for unconventional knowledge and adaptive intelligence; Robbery/Peer elements provide additional support. The harmful god is Eating God (when controlled by the Indirect Resource) and Wealth elements.

### Structure 7: 食神格 (Eating God Pattern) — High Determinism

The Eating God Pattern activates when the Main Qi (本气) of the Month Branch is the Day Master's Eating God element—the element the Day Master produces with the same Yin-Yang polarity[12]. For Jia Wood (Yang), Bing Fire (Yang) is Eating God; for Yi Wood (Yin), Ding Fire (Yin) is Eating God. Detection: Month Stem, Year Stem, Hour Stem.

The Eating God Pattern is broken by the appearance of strong Direct Officer elements that clash with the Eating God's rebellious output nature[35]. The pattern is also broken by Indirect Resource elements that control and suppress the Eating God's creative expression (the 枭神夺食 taboo again). The useful god is primarily the Eating God for creative expression and material output; secondarily, Wealth elements that receive the Eating God's productive energy. The Eating God pattern functions optimally when generating into Wealth in a clear elemental chain: Day Master → Eating God → Wealth. The harmful god is the Direct Officer (which directly opposes Eating God) and Indirect Resource (which suppresses Eating God).

### Structure 8: 伤官格 (Hurting Officer Pattern) — High Determinism

The Hurting Officer Pattern forms when the Main Qi (本气) of the Month Branch is the Day Master's Hurting Officer element—the element the Day Master produces with opposite Yin-Yang polarity[12][35]. For Jia Wood (Yang), Ding Fire (Yin) is Hurting Officer; for Yi Wood (Yin), Bing Fire (Yang) is Hurting Officer. Detection: Month Stem, Year Stem, Hour Stem.

The Hurting Officer Pattern is notoriously difficult to activate successfully and represents one of the most volatile configurations in BaZi theory. The pattern breaks fundamentally when any Direct Officer element appears in the chart, as Hurting Officer and Direct Officer directly oppose each other in the Ten God hierarchy[35][10]. The pattern also breaks when Indirect Resource controls Hurting Officer without compensation through Wealth. Remarkably, a high-quality Hurting Officer Pattern requires that no Direct Officer exists anywhere in the chart—this condition is termed 伤官伤尽 ("Hurting Officer completely dominates") and represents one of the most controversial and powerful patterns when it activates[50]. The useful god in a proper Hurting Officer Pattern is the Eating God (if the Day Master is strong) or Resource (if the Day Master is weak), with secondary support from Wealth. The harmful god is the Direct Officer and, in certain configurations, Indirect Resource.

## Month-Lord Special Structures: Precise Determinism

Beyond the eight regular patterns, two month-lord-specific structures occupy unique positions in the classical hierarchy due to their reliance on the Month Branch's specific position in the Twelve Growth Phases rather than hidden stem revelation through transparency.

### Structure 9: 建禄格 (Established Prosperity/Lu Pattern) — High Determinism

The Established Prosperity Pattern activates when the Earthly Branch of the Month Pillar occupies the Day Master's "Lu" position (临官) in the Twelve Growth Phases system[12][12]. The Lu position represents the stage of development where the element reaches full maturity and official capacity. The canonical correspondence table is absolute and deterministic: Jia Wood's Lu is Yin month (寅); Yi Wood's Lu is Mao month (卯); Bing Fire's Lu is Si month (巳); Ding Fire's Lu is Wu month (午); Wu Earth's Lu is Si month (巳); Ji Earth's Lu is Wu month (午); Geng Metal's Lu is Shen month (申); Xin Metal's Lu is You month (酉); Ren Water's Lu is Hai month (亥); Gui Water's Lu is Zi month (子)[12][36]. When the Month Branch matches this table value, and the Day Master is adequately rooted in its Lu, the pattern is established.

The Established Prosperity Pattern is broken when excessive Robbery or Peer elements appear without corresponding Officer or Wealth to direct their energy productively, or when the Day Master is fundamentally weak despite occupying its Lu (a condition indicating the root is insufficient)[12]. The useful god in an Established Prosperity Pattern is typically the Eating God or Wealth elements that channel the Day Master's abundant energy productively, or the Direct Officer that adds legitimacy to the prosperity. The harmful god is the Indirect Resource, which suppresses the Day Master's output channels.

### Structure 10: 月刃格 (Blade/Month Blade Pattern) — High Determinism

The Blade Pattern activates exclusively when the Earthly Branch of the Month Pillar occupies the Day Master's "Emperor/Prosperity" position (帝旺) in the Twelve Growth Phases, representing the absolute peak of elemental strength[12][12][36]. Critically, only Yang stems form true Blade Patterns in classical texts: Jia Wood's Blade is Mao month (卯); Bing Fire's Blade is Wu month (午); Wu Earth's Blade is Wu month (午); Geng Metal's Blade is You month (酉); Ren Water's Blade is Zi month (子). No Yin stems form Blade Patterns—Yi Wood in Mao, Ding Fire in Wu, Ji Earth in Wu, Xin Metal in You, and Gui Water in Zi all form regular Established Prosperity (建禄) patterns instead, not Blade patterns[12][36].

The Blade Pattern is substantially more intense than Established Prosperity and requires careful management. The pattern is broken when significant Robbery/Peer elements create internal dissension within the chart, or when Officer elements appear without Seal protection to moderate their force[12]. The useful god in a Blade Pattern is typically the Eating God (to express the excess strength productively), Officer elements (to add discipline and legitimacy), or Wealth (to consume the Day Master's abundant force). The harmful god is Indirect Resource and excessive Robbery.

## The Five Monoelement Specialized Patterns (一气格): Purity and Intensity

The five monoelement patterns represent a fundamentally different categorical logic from regular patterns. Rather than focusing on the Ten God relationship between the Day Master and the Month Branch's hidden stem, monoelement patterns require absolute or near-absolute dominance of a single element across the entire chart, with the Month Branch and all four Earthly Branches aligned to that element[18]. These patterns represent rare configurations requiring extraordinary elemental concentration.

### Structure 11: 曲直格 (Straightness and Flexibility / Wood Monoelement) — Medium Determinism

The Straightness-Flexibility Pattern activates when the Day Master is Jia or Yi Wood, the birth occurs during a Wood-dominant month (Yin or Mao month specifically), and either the entire chart forms a Wood monoelement through a three-branch harmonic combination (三合木局: Hai-Mao-Wei for Wood) or through a four-direction configuration (方局 for Wood: Yin-Mao-Chen all appearing). The detection rule requires that no more than one non-Wood element appears among the four Earthly Branches, and critically, that element must not be Metal (which controls Wood)[18]. The configuration is strengthened when Fire elements appear as secondary supporters (generating from Wood), and weakened when Earth or Metal elements disrupt the monoelement purity.

The Straightness-Flexibility Pattern breaks absolutely when Metal elements dominate or appear in multiple positions, as they directly oppose and dissipate the Wood element's cohesion. The pattern is also broken when a strong Fire element appears without receiving Water support, as this creates an imbalance in the generated elements. According to classical texts, the useful god in a pure Straightness-Flexibility Pattern is the Wood element itself for growth and productive momentum, with Fire as a secondary useful god for the generation chain, and water is a harmful god that exhausts Wood. The chart becomes problematic when Metal or Earth appear prominently.

### Structure 12: 炎上格 (Flaming Upward / Fire Monoelement) — Medium Determinism

The Flaming Upward Pattern emerges when the Day Master is Bing or Ding Fire, the birth occurs during a Fire-dominant month (Si or Wu month), and the entire chart manifests Fire monoelement purity through harmonic combination (三合火局: Yin-Wu-Xu) or directional combination (方局 for Fire: Si-Wu-Wei all present). No more than one non-Fire element may appear among the four Earthly Branches, and that element must not be Water (which extinguishes Fire)[18]. Earth elements enhance the pattern (Fire generates Earth), while Water elements destroy it.

The Flaming Upward Pattern breaks when Water appears at all prominently, or when strong Metal elements (Water generates Metal) create a chain that drains the Fire's strength without adequate compensation. The useful god is Fire for intensity and illumination, Earth as secondary useful god for generation support, and Water is a harmful god. Metal is also detrimental because it consumes the Fire's energy through the generation cycle.

### Structure 13: 稼穑格 (Cultivation and Harvest / Earth Monoelement) — Medium Determinism

The Cultivation-Harvest Pattern activates when the Day Master is Wu or Ji Earth, the birth occurs during an Earth-dominant month (Chen, Wei, Xu, or Chou), and the chart forms an Earth monoelement through the four-storage configuration (四库土: Chen-Wei-Xu-Chou all present together—note this is the unique four-branch earth combination rather than the standard three-branch harmonic). The pattern requires that all four Earthly Branches contain Earth elements or store Earth, with virtually no competing elements[18].

The Cultivation-Harvest Pattern breaks when Fire elements overwhelm the chart without adequate supporting elements, or when Wood elements appear prominently to dissipate the Earth's stability. The useful god is Earth for grounding stability and material accumulation, Fire for generation, and Wood is a harmful god (Wood controls Earth).

### Structure 14: 从革格 (Following Metal / Metal Monoelement) — Medium Determinism

The Following Metal Pattern emerges when the Day Master is Geng or Xin Metal, the birth occurs during a Metal-dominant month (Shen or You month), and the chart forms Metal monoelement through harmonic combination (三合金局: Si-You-Chou) or directional combination (方局 for Metal: Si-You-Xu all present)[18]. No more than one non-Metal element appears among the four Earthly Branches, and that element must not be Fire (which controls Metal).

The Following Metal Pattern breaks when Fire appears prominently, or when strong Earth elements (Metal generates Earth without adequate compensation) drain the Metal's controlling force. The useful god is Metal for sharpness and control, Water for generation support, and Fire is a harmful god. Wood also weakens the pattern by controlling Metal.

### Structure 15: 润下格 (Flowing Downward / Water Monoelement) — Medium Determinism

The Flowing Downward Pattern activates when the Day Master is Ren or Gui Water, the birth occurs during a Water-dominant month (Hai or Zi month, with Zi being absolutely essential for this pattern), and the chart forms Water monoelement through harmonic combination (三合水局: Shen-Zi-Chen all present) or maintains absolute water purity through multiple Water branches[18]. The pattern requires that the Month Branch is specifically Hai or Zi (with Zi being stronger); that Earthly Branches contain primarily Water elements (Zi, Hai, Chen); and that no more than one non-Water element appears among the four branches, which must not be Earth (which controls Water).

According to classical source materials and contemporary masters, the Flowing Downward Pattern functions optimally when Fire elements appear as secondary supporters (Water generates Wood generates Fire) to provide warmth and prevent the excessive cold and stagnation of pure water; if no Fire appears and no Wood appears, the chart becomes "cold-damp" and produces wealth without status (富而不贵)[18]. The pattern breaks absolutely when Earth elements dominate, as they directly oppose and dam the Water's flow. The useful god is Water for flow and adaptability, Metal for generation, and Earth is a harmful god.

## Transformation Patterns (化气格): Five Classical Stem Combinations — Medium-to-Low Determinism

Transformation patterns represent the most debated and conditional structures in classical BaZi literature because they require multiple simultaneous conditions: the two specified Heavenly Stems must appear adjacent in the four pillars (typically Day Stem combining with Month Stem or Hour Stem); the resulting transformed element must be supported by the Month Branch's seasonal energy; and no disrupting elements can override the transformation's fragile establishment[12][12]. The five canonical stem combinations are absolute across all classical texts:

| Original Stems | Transformed Element | Canonical Source |
|---|---|---|
| 甲己 | 土 (Earth) | 三命通会, 渊海子平 |
| 乙庚 | 金 (Metal) | 三命通会, 渊海子平 |
| 丙辛 | 水 (Water) | 三命通会, 渊海子平 |
| 丁壬 | 木 (Wood) | 三命通会, 渊海子平 |
| 戊癸 | 火 (Fire) | 三命通会, 渊海子平 |

### Structure 16: 化土格 (Transformation to Earth: Jia-Ji Combination) — Low Determinism

The Jia-Ji Transformation Pattern activates when a Jia Stem and a Ji Stem appear adjacent in the four pillars (most commonly Day Stem Jia combining with Month or Hour Stem Ji), and the Month Branch's Main Qi supports Earth through being of Earth element (Chen, Wei, Xu, or Chou)[12][12]. When transformation occurs, the Day Stem effectively shifts from Wood function to Earth function, and analysis must be conducted as if the Day Master is now Earth rather than Wood.

Deterministic detection for true transformation versus false transformation (假化) requires verification that: (1) the two stems are genuinely adjacent (same pillar or consecutive pillars); (2) the Month Branch's primary energy supports Earth, not opposes it; (3) no strong Metal element appears in the chart to control the transformed Earth and prevent its establishment; (4) the combination direction is appropriate (Jia yielding to Ji, not vice versa, because Jia is Yang and Ji is Yin, creating natural combination potential)[12]. The transformation breaks when strong Wood elements appear without Earth generation, as this indicates the Jia's original nature is unsubdued. The useful god becomes Earth-related gods rather than Wood-related gods.

### Structure 17: 化金格 (Transformation to Metal: Yi-Geng Combination) — Low Determinism

The Yi-Geng Transformation Pattern emerges when Yi and Geng Stems appear adjacent (typically Yi Day Stem with Geng Month or Hour Stem), and the Month Branch's Main Qi supports Metal element (Shen or You months specifically)[12][12]. When transformation achieves true status (真化), the Day Master functions as Metal rather than Wood, triggering complete reanalysis.

Conditions for true transformation: (1) stems must be adjacent; (2) Month Branch must be Shen or You; (3) no excessive Wood elements to reassert Yi's original nature; (4) no strong Fire elements to control the transformed Metal and prevent its stability[12]. The pattern breaks when strong Wood elements overwhelm the chart or when the Metal element lacks support. The useful god becomes Metal-focused rather than Wood-focused.

### Structure 18: 化水格 (Transformation to Water: Bing-Xin Combination) — Low Determinism

The Bing-Xin Transformation Pattern activates when Bing and Xin Stems appear adjacent (Bing Day Stem typically combining with Xin Month or Hour Stem), and the Month Branch's Main Qi supports Water (Hai or Zi months)[12][12]. True transformation conditions require adjacency, Water-dominant month branch, and absence of strong Fire elements that would prevent the transformation's establishment.

When transformation occurs, the Day Master functions as Water rather than Fire, completely reorienting the Ten God analysis. The pattern breaks when strong Fire elements dominate without adequate Water support or generation. The useful god becomes Water-focused, and all Fire-related analysis is invalidated.

### Structure 19: 化木格 (Transformation to Wood: Ding-Ren Combination) — Low Determinism

The Ding-Ren Transformation Pattern emerges when Ding and Ren Stems appear adjacent (Ding Day Stem with Ren Month or Hour Stem), and the Month Branch's Main Qi supports Wood (Yin or Mao months)[12][12]. True conditions: adjacency, Wood-dominant month, and absence of overwhelming Metal elements.

When transformation achieves true status, the Day Master functions as Wood and all Ding-Fire analysis is suspended. The pattern breaks when strong Metal elements control or strong Fire elements dominate the chart without adequate Wood support. The useful god becomes Wood-focused.

### Structure 20: 化火格 (Transformation to Fire: Wu-Gui Combination) — Low Determinism

The Wu-Gui Transformation Pattern activates when Wu and Gui Stems appear adjacent (Wu Day Stem with Gui Month or Hour Stem typically), and the Month Branch's Main Qi supports Fire (Si or Wu months)[12][12]. True transformation requires adjacency, Fire-dominant month, and absence of strong Water elements.

When transformation succeeds, the Day Master functions as Fire rather than Earth, requiring complete reanalysis of the chart's structure. The pattern breaks when strong Water elements overwhelm the transformation or when strong Earth elements dominate without adequate Fire support. The useful god becomes Fire-focused.

## Following Patterns (从格): Five Structures of Yielding — Medium Determinism

Following patterns represent a fundamentally different logical framework from regular patterns: instead of the Day Master maintaining independent status and analyzing other elements relative to the Day Master, Following patterns establish that the Day Master is so weak (lacking roots, lacking supporting elements) that it abandons its own identity and "follows" the dominant element in the chart[20][24]. When a Following pattern is genuine (真从), the entire analytical system shifts from "Day Master as reference point" to "Dominant Element as reference point," and the useful gods become the supporting elements of the dominant force rather than supports for the weakened Day Master.

The canonical criterion for genuine Following versus false Following (假从) is absolute: genuine Following requires that the Day Master possess absolutely no roots or support anywhere in the four pillars. This means the Day Master's element does not appear in any Earthly Branch at all, does not have any Heavenly Stem of the same element (Peer/Robbery), and does not have any meaningful production element (Seal/Resource) to sustain it[12][12][24]. If even a single root exists (such as the Day Master appearing as a hidden stem in a branch, or a single Seal element present), the chart is false Following and must be analyzed as a regular pattern instead.

### Structure 21: 从财格 (Following Wealth) — Medium Determinism

The Following Wealth Pattern activates when the Day Master is so weak that it cannot oppose the Wealth element, which dominates the chart through multiple appearances or overwhelming strength[24]. For detection, verify: (1) Day Master has absolutely no roots or support; (2) Wealth elements dominate through multiple stems or strong branch roots; (3) the Month Branch contains the Day Master's Wealth element, not another element (ensuring seasonal support for the dominant force); (4) no Officer or Seal elements appear prominently to disrupt the Wealth's dominance.

When genuine, the useful god becomes the Wealth element and any Eating God/Hurting Officer that generates Wealth into further productive cycles (食伤生财), not supports for the weakened Day Master. The harmful god becomes the Seal/Resource elements (which oppose Wealth) and any significant Robbery/Peer (which competes for the Wealth). According to source materials, Following Wealth charts that experience favorable Wealth luck periods achieve remarkable prosperity[20]; however, entering unfavorable periods (especially Seal periods) produces catastrophic collapse because the chart has no internal stability or self-defense mechanism.

### Structure 22: 从官格 (Following Officer) — Medium Determinism

The Following Officer Pattern forms when the Day Master is absolutely weak and the Officer elements (either Direct Officer or Seven Killings, typically combined and balanced) dominate the chart through multiple prominent appearances[24]. Detection requires: (1) absolute Day Master weakness; (2) Officer elements dominate through multiple stems and strong branch roots; (3) Month Branch supports Officer elements; (4) Eating God/Hurting Officer elements do not appear prominently to attack Officers; (5) Wealth elements appear in moderate quantities to support the Officer chain.

When genuine, the useful god becomes the Officer elements and Wealth (which generates Officer), not the Day Master's support. The harmful god is Eating God/Hurting Officer (which directly attacks Officer), Seal/Resource (which disrupts the Wealth-Officer generation chain), and Robbery/Peer without compensation. Following Officer charts typically indicate individuals subject to external authority and control; their fortune rises with favorable authority periods and collapses during Eating God periods when they offend superiors.

### Structure 23: 从儿格 (Following Output/Children) — Medium Determinism

The Following Output Pattern activates when the Day Master is absolutely weak and the Output elements (Eating God and/or Hurting Officer) dominate the chart through overwhelming presence[24]. Detection requires: (1) absolute Day Master weakness; (2) Output elements dominate multiple stems and branches; (3) Month Branch supports Output; (4) Seal/Resource elements do not appear significantly (which would suppress Output); (5) Wealth appears moderately to receive the Output's energy.

When genuine, the useful god becomes Output and Wealth (which receives Output), not the Day Master's supports. The harmful god is Seal/Resource (which controls Output), Officer elements (which disrupt the natural output expression), and Robbery/Peer without productive outlet. Following Output charts indicate creative, expressive individuals; their fortune depends on productive periods where their talents are valued, and they suffer during Seal periods when their expression is suppressed.

### Structure 24: 从势格 (Following Momentum/Combined Dominance) — Medium Determinism

The Following Momentum Pattern, also termed "Following Trend," emerges when the Day Master is absolutely weak and multiple dominant elements (typically a combination of Wealth, Officer, and Output in balanced quantities) all dominate simultaneously, forcing the Day Master to follow the chart's overall momentum rather than a single element[24]. This represents a more complex version of Following patterns where the dominant force is not a single element but rather a coordinated elemental configuration.

Detection requires: (1) absolute Day Master weakness; (2) multiple dominant elements all present in substantial quantities; (3) these elements are not in conflict but rather support each other through generation cycles; (4) no single element is suppressed; (5) the Month Branch supports the overall momentum configuration rather than opposing it. The useful god becomes the entire dominant configuration and the productive cycles that bind them. The harmful god is any element that disrupts or opposes the coordinated dominance. Following Momentum charts are somewhat flexible compared to single-element Following patterns, as they have multiple avenues for maintaining fortune, but they remain fundamentally dependent on external conditions.

### Structure 25: 从强格 (Following Strength/Extreme Prosperity) — Medium-to-Low Determinism

The Following Strength Pattern, also called "Following Prosperity" (从旺), represents an edge case where the Day Master is absolutely weak but becomes so not through explicit dominance of another element but rather through the simultaneous elimination of all opposing elements and the absolute supremacy of the Day Master's own element in overwhelming concentration[24]. This differs from the other Following patterns because instead of following a different element, the Day Master "follows" its own element's extreme dominance.

Detection requires: (1) Day Master has no support elements; (2) the Day Master's own element appears in extreme concentration (multiple hidden roots, multiple branches containing the element); (3) no opposing elements appear at all; (4) the configuration is so imbalanced that the Day Master cannot reduce this excess and thus "follows" it as a following pattern. The useful god becomes the same element (further strengthening) and any output elements that consume this excess productively. The harmful god is any element that opposes or controls the dominant element. This pattern is rare and represents a specialized case of extreme elemental imbalance.

## Exotic and Specialized Structures (Esoteric Patterns) — Low-to-Very-Low Determinism

Beyond the primary structures enumerated above, classical BaZi texts reference approximately 10–20 additional specialized patterns that occupy niche positions in chart analysis, typically involving specific branch combinations, celestial stems, or rare configurations. These structures are documented in classical texts but require substantially more subjective judgment than the 25 structures outlined above, and many generate significant interpretive debate among practitioners[50].

### Structure 26: 魁罡格 (Kuei-Gang / Celestial Integrity Pattern) — Medium Determinism

The Kuei-Gang Pattern emerges when the Day Stem is one of four specific celestial stems (Geng, Xin, Ren, or Gui) and the Day Branch is one of four specific branches (Chen, Wei, Xu, or Chou) in particular combinations[50]. The specific valid Day Pillar combinations are: Geng-Chen (庚辰), Xin-Wei (辛未), Ren-Xu (壬戌), Gui-Chou (癸丑). According to classical texts, when one of these four pillars is the actual Day Pillar, the native possesses a stern, authoritative, and potentially dangerous disposition; the pattern indicates someone with strong backbone but prone to rigidity and defiance of normal rules.

The Kuei-Gang Pattern breaks when Robbery or Peer elements appear prominently without Officer control, or when Seal elements overwhelm the Day Master, disrupting its authority. Detection is straightforward and deterministic: simply check if the Day Pillar matches one of the four canonical combinations. The determinism rating is high because detection requires no complex elemental analysis, though interpretation of its effects requires medium-level judgment about how to integrate it with other structural patterns.

### Structure 27: 拱禄格 (Embracing Lu/Arch Lu) — Low-to-Medium Determinism

The Arch Lu Pattern occurs when the Day Master's Lu position appears not in the Month Branch itself but instead is "embraced" or "arched" between the Year and Hour branches through a specific branch combination (such as the Day Master's Lu appearing hidden within a trining or arching configuration of surrounding branches)[50]. For example, if the Day Master is Jia Wood with Lu in Yin, but Yin does not appear as the Month Branch, yet both Zi (before Yin in the cycle) and Mao (after Yin in the cycle) appear in Year and Hour positions, the Lu is considered "embraced" between them.

Detection requires identification of the Day Master's Lu position, verification that the Lu branch does not appear in the Month position, and confirmation that the branches immediately before and after the Lu in the twelve-branch cycle both appear in the four pillars. The determinism level is low-to-medium because branch-embracing logic involves cyclical positioning that can be complex; however, once the canonical embracing combinations are mapped, detection becomes algorithmic.

### Structure 28: 飞天禄马倒冲 (Flying Heaven Lu-Horse, Reverse Clash) — Low Determinism

The Flying Heaven pattern involves the simultaneous appearance of celestial stems and horseback stems in specific configurations that "fly upward" to heaven (meaning the influence extends beyond normal personal circumstances to touch celestial or administrative matters)[50]. The Reverse Clash variation (倒冲) occurs when the normal clash between branches is inverted or reversed, producing paradoxical outcomes such as simultaneous opportunity and obstruction, or outcomes that appear negative but produce positive results.

Detection of Flying Heaven patterns requires identification of specific stem-branch combinations associated with celestial elevation and verification of clash reversal through detailed branch-interaction analysis. The determinism level is very low because these patterns involve esoteric symbolic interpretations that classical texts themselves debate; multiple authoritative interpretations exist for the same configuration.

### Structure 29-30: Two-God Image (两神成象) and Child-Chen Dual Beauty (子辰双美格) — Very Low Determinism

The Two-God Image pattern and the Child-Chen Dual Beauty pattern represent extremely rare and highly specialized structures that emerge from specific celestial stem and branch combinations with cultural or symbolic significance[50]. These patterns are documented in classical texts but generate substantial disagreement about detection criteria and interpretation; they are typically only relevant in advanced or esoteric BaZi practice rather than standard computational analysis. For the purposes of a computational implementation, these patterns should be flagged with very-low-determinism ratings and deferred to manual expert review if detected, as their occurrence is rare and their proper handling requires master-level knowledge.

## Hidden Stem Canon Table (月支藏干): Deterministic Foundation

The following table presents the canonical hidden stem configuration of all twelve Earthly Branches according to classical sources (三命通会, 渊海子平, and contemporary authoritative texts). This table is the immutable foundation upon which all structure detection depends:

| Month Branch | Chinese Name | Main Qi (本气) | Middle Qi (中气) | Residual Qi (余气) | Main Qi Element | Middle Qi Element | Residual Qi Element | Qi Strength Ratio |
|---|---|---|---|---|---|---|---|---|
| 寅 (Yin/Tiger) | Spring Commencement | 甲 Jia | 丙 Bing | 戊 Wu | Yang Wood | Yang Fire | Yang Earth | 60-30-10 |
| 卯 (Mao/Rabbit) | Peak Spring | 乙 Yi | — | — | Yin Wood | — | — | 100 (pure) |
| 辰 (Chen/Dragon) | Spring Conclusion | 戊 Wu | 乙 Yi | 癸 Gui | Yang Earth | Yin Wood | Yin Water | 60-30-10 |
| 巳 (Si/Snake) | Summer Commencement | 丙 Bing | 戊 Wu | 庚 Geng | Yang Fire | Yang Earth | Yang Metal | 60-30-10 |
| 午 (Wu/Horse) | Peak Summer | 丁 Ding | 己 Ji | — | Yin Fire | Yin Earth | — | 60-40 (pure) |
| 未 (Wei/Goat) | Summer Conclusion | 己 Ji | 丁 Ding | 乙 Yi | Yin Earth | Yin Fire | Yin Wood | 60-30-10 |
| 申 (Shen/Monkey) | Autumn Commencement | 庚 Geng | 壬 Ren | 戊 Wu | Yang Metal | Yang Water | Yang Earth | 60-30-10 |
| 酉 (You/Rooster) | Peak Autumn | 辛 Xin | — | — | Yin Metal | — | — | 100 (pure) |
| 戌 (Xu/Dog) | Autumn Conclusion | 戊 Wu | 辛 Xin | 丁 Ding | Yang Earth | Yin Metal | Yin Fire | 60-30-10 |
| 亥 (Hai/Pig) | Winter Commencement | 壬 Ren | 甲 Jia | — | Yang Water | Yang Wood | — | 70-30 |
| 子 (Zi/Rat) | Peak Winter | 癸 Gui | — | — | Yin Water | — | — | 100 (pure) |
| 丑 (Chou/Ox) | Winter Conclusion | 己 Ji | 癸 Gui | 辛 Xin | Yin Earth | Yin Water | Yin Metal | 60-30-10 |

## Ten God Determination Matrix: Deterministic Generation

The following matrix presents the deterministic calculation of Ten God relationships for all ten Heavenly Stems and all five-element-based controls/productions:

| Day Master | Controls (克) | Controlled By (被克) | Produces (生) | Produced By (被生) | Same Polarity Support (比) | Opposite Polarity Support (劫) |
|---|---|---|---|---|---|---|
| 甲 Jia (Y-Wood) | 己 Ji (Y-Earth) [Direct Wealth] / 戊 Wu (Y-Earth) [Indirect Wealth] | 庚 Geng (Y-Metal) [7-Kill] / 辛 Xin (Y-Metal) [Direct Officer] | 丙 Bing (Y-Fire) [Eating God] / 丁 Ding (Y-Fire) [Hurting Officer] | 壬 Ren (Y-Water) [Direct Resource] / 癸 Gui (Y-Water) [Indirect Resource] | 甲 Jia (Friend) | 乙 Yi (Rob Wealth) |
| 乙 Yi (Y-Wood) | 戊 Wu (Y-Earth) [Direct Wealth] / 己 Ji (Y-Earth) [Indirect Wealth] | 辛 Xin (Y-Metal) [7-Kill] / 庚 Geng (Y-Metal) [Direct Officer] | 丁 Ding (Y-Fire) [Eating God] / 丙 Bing (Y-Fire) [Hurting Officer] | 癸 Gui (Y-Water) [Direct Resource] / 壬 Ren (Y-Water) [Indirect Resource] | 乙 Yi (Friend) | 甲 Jia (Rob Wealth) |
| 丙 Bing (Y-Fire) | 辛 Xin (Y-Metal) [Direct Wealth] / 庚 Geng (Y-Metal) [Indirect Wealth] | 壬 Ren (Y-Water) [7-Kill] / 癸 Gui (Y-Water) [Direct Officer] | 戊 Wu (Y-Earth) [Eating God] / 己 Ji (Y-Earth) [Hurting Officer] | 甲 Jia (Y-Wood) [Direct Resource] / 乙 Yi (Y-Wood) [Indirect Resource] | 丙 Bing (Friend) | 丁 Ding (Rob Wealth) |
| 丁 Ding (Y-Fire) | 庚 Geng (Y-Metal) [Direct Wealth] / 辛 Xin (Y-Metal) [Indirect Wealth] | 癸 Gui (Y-Water) [7-Kill] / 壬 Ren (Y-Water) [Direct Officer] | 己 Ji (Y-Earth) [Eating God] / 戊 Wu (Y-Earth) [Hurting Officer] | 乙 Yi (Y-Wood) [Direct Resource] / 甲 Jia (Y-Wood) [Indirect Resource] | 丁 Ding (Friend) | 丙 Bing (Rob Wealth) |
| 戊 Wu (Y-Earth) | 癸 Gui (Y-Water) [Direct Wealth] / 壬 Ren (Y-Water) [Indirect Wealth] | 甲 Jia (Y-Wood) [7-Kill] / 乙 Yi (Y-Wood) [Direct Officer] | 庚 Geng (Y-Metal) [Eating God] / 辛 Xin (Y-Metal) [Hurting Officer] | 丙 Bing (Y-Fire) [Direct Resource] / 丁 Ding (Y-Fire) [Indirect Resource] | 戊 Wu (Friend) | 己 Ji (Rob Wealth) |
| 己 Ji (Y-Earth) | 壬 Ren (Y-Water) [Direct Wealth] / 癸 Gui (Y-Water) [Indirect Wealth] | 乙 Yi (Y-Wood) [7-Kill] / 甲 Jia (Y-Wood) [Direct Officer] | 辛 Xin (Y-Metal) [Eating God] / 庚 Geng (Y-Metal) [Hurting Officer] | 丁 Ding (Y-Fire) [Direct Resource] / 丙 Bing (Y-Fire) [Indirect Resource] | 己 Ji (Friend) | 戊 Wu (Rob Wealth) |
| 庚 Geng (Y-Metal) | 乙 Yi (Y-Wood) [Direct Wealth] / 甲 Jia (Y-Wood) [Indirect Wealth] | 丙 Bing (Y-Fire) [7-Kill] / 丁 Ding (Y-Fire) [Direct Officer] | 癸 Gui (Y-Water) [Eating God] / 壬 Ren (Y-Water) [Hurting Officer] | 戊 Wu (Y-Earth) [Direct Resource] / 己 Ji (Y-Earth) [Indirect Resource] | 庚 Geng (Friend) | 辛 Xin (Rob Wealth) |
| 辛 Xin (Y-Metal) | 甲 Jia (Y-Wood) [Direct Wealth] / 乙 Yi (Y-Wood) [Indirect Wealth] | 丁 Ding (Y-Fire) [7-Kill] / 丙 Bing (Y-Fire) [Direct Officer] | 壬 Ren (Y-Water) [Eating God] / 癸 Gui (Y-Water) [Hurting Officer] | 己 Ji (Y-Earth) [Direct Resource] / 戊 Wu (Y-Earth) [Indirect Resource] | 辛 Xin (Friend) | 庚 Geng (Rob Wealth) |
| 壬 Ren (Y-Water) | 丁 Ding (Y-Fire) [Direct Wealth] / 丙 Bing (Y-Fire) [Indirect Wealth] | 戊 Wu (Y-Earth) [7-Kill] / 己 Ji (Y-Earth) [Direct Officer] | 甲 Jia (Y-Wood) [Eating God] / 乙 Yi (Y-Wood) [Hurting Officer] | 庚 Geng (Y-Metal) [Direct Resource] / 辛 Xin (Y-Metal) [Indirect Resource] | 壬 Ren (Friend) | 癸 Gui (Rob Wealth) |
| 癸 Gui (Y-Water) | 丙 Bing (Y-Fire) [Direct Wealth] / 丁 Ding (Y-Fire) [Indirect Wealth] | 己 Ji (Y-Earth) [7-Kill] / 戊 Wu (Y-Earth) [Direct Officer] | 乙 Yi (Y-Wood) [Eating God] / 甲 Jia (Y-Wood) [Hurting Officer] | 辛 Xin (Y-Metal) [Direct Resource] / 庚 Geng (Y-Metal) [Indirect Resource] | 癸 Gui (Friend) | 壬 Ren (Rob Wealth) |

## Determinism Levels and Confidence Ratings

The following classification establishes the determinism rating for each structure type:

| Determinism Level | Definition | Example Structures | Confidence for Computational Implementation |
|---|---|---|---|
| High | Detection criteria are absolute with no subjective judgment required; the structure either is or is not present based on mechanical checks | Regular Patterns (正格), Established Prosperity (建禄), Blade (月刃), Transformation Patterns (化气格) with canonical conditions met | Canonical - implement immediately with no override mechanism |
| Medium | Detection criteria involve some subjective assessment of element strength or threshold-crossing, but objective computational checks can establish clear boundaries | Following Patterns (从格) with weakness thresholds, Monoelement Patterns (一气格) with purity percentage requirements, Some specialized patterns | Common - implement with clear threshold parameters; document threshold choices |
| Low | Detection involves complex interaction assessment, multiple conditional pathways, or significant classical text debate about which configuration qualifies | Exotic Patterns (Kuei-Gang variations), Pattern quality assessment (破格 analysis), Some esoteric structures | Rare - implement as detection flags for manual expert review; defer detailed analysis to expert layer |
| Very Low | Detection and interpretation require master-level knowledge; classical texts debate fundamentals of the pattern's existence or criteria | Flying Heaven patterns, Two-God Image, Esoteric celestial configurations | Deferred - flag for expert review; do not attempt computational analysis |

## Comprehensive CSV Reference Table: Structure Master Index

The following CSV table consolidates all 30+ structures with their essential detection parameters:

```
id,name_zh,name_pinyin,name_en,category,day_master_types,month_branch_requirements,hidden_stem_requirement,key_detection_rule,break_conditions,useful_god_cn,harmful_god_cn,determinism_level,source_book,confidence_rating
1,正官格,Zheng Guan Ge,Direct Officer Pattern,正格,Any,Any,Main Qi = Day Master's Direct Officer,Officer element reveals in Year/Month/Hour stem; opposite polarity to DM,Month Branch Main Qi appears in celestial stems,Direct Officer + Wealth,Eating God + Hurting Officer,High,三命通会/渊海子平,Canonical
2,七杀格,Qi Sha Ge,Seven Killings Pattern,正格,Any,Any,Main Qi = Day Master's Seven Killings,Killings element reveals in Year/Month/Hour stem; same polarity as DM,No Eating God without Seal; no excessive Robbery,Seven Killings + Wealth,Eating God + Hurting Officer,High,三命通会/渊海子平,Canonical
3,正财格,Zheng Cai Ge,Direct Wealth Pattern,正格,Any,Any,Main Qi = Day Master's Direct Wealth,Wealth element (opposite polarity) reveals in celestial stems,No strong Seal without consumption; no excessive Robbery,Direct Wealth + Eating God,Seal/Resource,High,三命通会/渊海子平,Canonical
4,偏财格,Pian Cai Ge,Indirect Wealth Pattern,正格,Any,Any,Main Qi = Day Master's Indirect Wealth,Wealth element (same polarity) reveals in celestial stems,No strong Seal; manageable Robbery tolerance,Indirect Wealth + Hurting Officer,Seal/Resource,High,三命通会/渊海子平,Canonical
5,正印格,Zheng Yin Ge,Direct Resource/Seal Pattern,正格,Any,Any,Main Qi = Day Master's Direct Resource,Resource element (opposite polarity) reveals in celestial stems,Critical: no Wealth element; no excess Robbery,Direct Resource + Robbery/Peer,Wealth (taboo: 贪财坏印),High,三命通会/渊海子平,Canonical
6,偏印格,Pian Yin Ge,Indirect Resource Pattern,正格,Any,Any,Main Qi = Day Master's Indirect Resource,Resource element (same polarity) reveals in celestial stems,No Eating God control by Indirect Resource (枭神夺食 taboo),Indirect Resource + Robbery,Eating God + Wealth,High,三命通会/渊海子平,Canonical
7,食神格,Shi Shen Ge,Eating God Pattern,正格,Any,Any,Main Qi = Day Master's Eating God,Eating God element (same polarity) reveals in celestial stems,No Direct Officer clash; no Indirect Resource suppression,Eating God + Wealth generation chain,Direct Officer + Indirect Resource,High,三命通会/渊海子平,Canonical
8,伤官格,Shang Guan Ge,Hurting Officer Pattern,正格,Any,Any,Main Qi = Day Master's Hurting Officer,Hurting Officer element (opposite polarity) reveals in celestial stems; no Direct Officer anywhere,Direct Officer absolutely forbidden; Indirect Resource may suppress without Wealth,Eating God or Resource (context-dependent),Direct Officer,High,三命通会/渊海子平,Canonical
9,建禄格,Jian Lu Ge,Established Prosperity Pattern,月令特殊,Jia-癸,Month Branch = DM's Lu position; see mapping table,N/A - Month Branch position determines,Month pillar IS the Lu position (不看hidden stem; check branch directly),No excessive Robbery; DM must have real root in Lu,Eating God or Wealth to channel excess; Direct Officer,Indirect Resource,High,三命通会/渊海子平,Canonical
10,月刃格,Yue Ren Ge,Blade/Month Blade Pattern,月令特殊,Only Yang stems: Jia/Bing/Wu/Geng/Ren,Month Branch = DM's Emperor position (帝旺); NO Yin stems,N/A,Month pillar MUST be Emperor position for Yang DM only; Yin stems form Jian Lu instead,Excessive Robbery creates internal conflict; Officer without Seal,Eating God or Officer or Wealth,Indirect Resource,High,三命通会/渊海子平,Canonical
11,曲直格,Qu Zhi Ge,Straightness-Flexibility/Wood Monoelement,一气格,甲 or 乙,Yin or Mao month; three-branch Wood harmony (Hai-Mao-Wei or Yin-Mao-Chen) OR four-direction (Yin-Mao-Chen all present),All four branches Wood element or form Wood harmonic,≤1 non-Wood branch; must not be Metal; Fire is supporting element,Metal dominance; strong Fire without Water support,Wood + Fire generation,Metal + Earth,Medium,三命通会/渊海子平,Canonical
12,炎上格,Yan Shang Ge,Flaming Upward/Fire Monoelement,一气格,丙 or 丁,Si or Wu month; three-branch Fire harmony (Yin-Wu-Xu) OR four-direction (Si-Wu-Wei all present),All four branches Fire element or form Fire harmonic,≤1 non-Fire branch; must not be Water; Earth is supporting element,Water dominance; strong Metal chain draining Fire,Fire + Earth generation,Water + Metal,Medium,三命通会/渊海子平,Canonical
13,稼穑格,Jia Se Ge,Cultivation-Harvest/Earth Monoelement,一气格,戊 or 己,Chen/Wei/Xu/Chou month; four-storage Earth complete (Chen-Wei-Xu-Chou all present simultaneously),All four branches contain Earth storage,All four branches MUST be the four storages (Chen-Wei-Xu-Chou),Overwhelming Fire without support; strong Wood control,Earth + Fire generation,Wood,Medium,三命通会/渊海子平,Canonical
14,从革格,Cong Ge Ge,Following Metal/Metal Monoelement,一气格,庚 or 辛,Shen or You month; three-branch Metal harmony (Si-You-Chou) OR four-direction (Si-You-Xu all present),All four branches Metal element or form Metal harmonic,≤1 non-Metal branch; must not be Fire; Water is supporting element,Fire dominance; strong Earth drain without compensation,Metal + Water generation,Fire + Wood,Medium,三命通会/渊海子平,Canonical
15,润下格,Run Xia Ge,Flowing Downward/Water Monoelement,一气格,壬 or 癸,Hai or Zi month (Zi preferred for strength); three-branch Water harmony (Shen-Zi-Chen) OR Zi dominance,All four branches Water element or form Water harmonic; Month MUST be Hai or Zi,≤1 non-Water branch; must not be Earth; Fire/Wood presence for warmth prevents coldness,Earth control; pure coldness without Fire (wealthy but not noble),Water + Metal generation; Fire for warmth,Earth + Wood control,Medium,三命通会/渊海子平,Canonical
16,化土格,Hua Tu Ge,Transformation to Earth (Jia-Ji combination),化气格,Must include Jia stem in Day Master position; Ji must appear in Month or Hour,Month branch must be Earth element (Chen/Wei/Xu/Chou),Jia and Ji stems adjacent (typically Day Stem Jia combining with Month/Hour Stem Ji),Two stems adjacent; Month Branch supports Earth; no strong Metal control disrupting transformation; transformation verified through absence of Wood dominance,Strong Wood elements indicating Jia's original nature unsubdued; Metal control of transformed Earth,Earth-focused gods (formerly Wood analysis suspended),Wood-focused gods,Low,三命通会/渊海子平,Common
17,化金格,Hua Jin Ge,Transformation to Metal (Yi-Geng combination),化气格,Must include Yi stem in Day Master position; Geng must appear in Month or Hour,Month branch must be Metal element (Shen or You specifically),Yi and Geng stems adjacent (typically Day Stem Yi with Month/Hour Stem Geng),Two stems adjacent; Month Branch = Shen or You; no overwhelming Wood elements; no strong Fire to control transformed Metal,Excessive Wood reasserting Yi's original Wood nature; Fire elements disrupting Metal transformation,Metal-focused gods (formerly Wood analysis suspended),Wood-focused gods,Low,三命通会/渊海子平,Common
18,化水格,Hua Shui Ge,Transformation to Water (Bing-Xin combination),化气格,Must include Bing stem in Day Master position; Xin must appear in Month or Hour,Month branch must be Water element (Hai or Zi),Bing and Xin stems adjacent (typically Day Stem Bing with Month/Hour Stem Xin),Two stems adjacent; Month Branch = Hai or Zi; no strong Fire elements disrupting transformation; no overwhelming supporting Water chains,Strong Fire elements preventing transformation establishment; lack of Water support,Water-focused gods (formerly Fire analysis suspended),Fire-focused gods,Low,三命通会/渊海子平,Common
19,化木格,Hua Mu Ge,Transformation to Wood (Ding-Ren combination),化气格,Must include Ding stem in Day Master position; Ren must appear in Month or Hour,Month branch must be Wood element (Yin or Mao),Ding and Ren stems adjacent (typically Day Stem Ding with Month/Hour Stem Ren),Two stems adjacent; Month Branch = Yin or Mao; no overwhelming Metal elements; no strong Fire dominance disrupting,Strong Metal elements controlling or preventing Wood transformation; Fire overwhelming without support,Wood-focused gods (formerly Fire analysis suspended),Fire-focused gods,Low,三命通会/渊海子平,Common
20,化火格,Hua Huo Ge,Transformation to Fire (Wu-Gui combination),化气格,Must include Wu stem in Day Master position; Gui must appear in Month or Hour,Month branch must be Fire element (Si or Wu),Wu and Gui stems adjacent (typically Day Stem Wu with Month/Hour Stem Gui),Two stems adjacent; Month Branch = Si or Wu; no strong Water elements disrupting transformation; transformation verified,Strong Water elements overwhelming transformation or causing reversion; insufficient Fire support,Fire-focused gods (formerly Earth analysis suspended),Water-focused gods,Low,三命通会/渊海子平,Common
21,从财格,Cong Cai Ge,Following Wealth Structure,从格,Any weak DM,Wealth element appears in Month Branch; no Officer/Seal dominance,DM has absolutely no roots (no same-element in any branch; no Seal element meaningful presence),DM absolutely weak (no roots); Wealth dominates multiple stems/branches; Month supports Wealth; no Officer attack,Officer/Seal elements disrupting Wealth dominance; Robbery competing for Wealth without Officer control,Wealth + Eating God/Hurting Officer generation,Seal/Resource + Robbery/Peer,Medium,渊海子平/三命通会,Common
22,从官格,Cong Guan Ge,Following Officer Structure,从格,Any weak DM,Officer elements (Direct or Killings) appear in Month Branch; Wealth present moderately,DM has absolutely no roots; Officer elements dominate multiple stems/branches,DM absolutely weak; Officer dominates chart; Month supports Officer; Wealth appears moderately (generating Officer); Eating God does not dominate,Eating God/Hurting Officer attack on Officers; Seal breaking Wealth-Officer chain; excessive Robbery,Officer + Wealth generation,Eating God/Hurting Officer + Seal/Resource,Medium,渊海子平/三命通会,Common
23,从儿格,Cong Er Ge,Following Output/Children Structure,从格,Any weak DM,Output elements (Eating God/Hurting Officer) appear in Month Branch; Wealth present moderately,DM absolutely weak; Output elements dominate multiple stems/branches,DM absolutely weak; Output dominates chart; Month supports Output; Wealth appears moderately; Seal does not suppress,Seal/Resource suppressing Output; Officer disrupting output expression; Robbery without productive outlet,Output + Wealth generation,Seal/Resource + Officer,Medium,渊海子平/三命通会,Common
24,从势格,Cong Shi Ge,Following Momentum/Combined Dominance,从格,Any weak DM,Multiple dominant elements (Wealth+Officer+Output) coordinated in Month and pillars; none suppressed,DM absolutely weak; multiple elements balanced in dominance,DM absolutely weak; multiple elements all present; supportive generation cycles; Month supports overall momentum; no single element suppressed,Single element disrupting the coordinated dominance; one element overwhelming others,Entire dominant configuration and productive cycles binding them,Any element opposing or controlling the coordinated dominance,Medium,渊海子平/三命通会,Common
25,从强格,Cong Qiang Ge,Following Strength/Extreme Prosperity,从格,Any weak DM,Same element appears in overwhelming concentration (multiple hidden roots; DM element dominates Month and multiple branches),DM weak but element appears in extreme concentration,DM no support; DM's own element in extreme concentration; no opposing elements present; imbalanced to extreme degree,Opposing elements appearing; any element controlling or weakening the dominant same-element concentration,Same element (further strengthening) + Output elements consuming excess productively,Any controlling/opposing element,Low,渊海子平/三命通会,Rare
26,魁罡格,Kuei Gang Ge,Celestial Integrity/Kuei-Gang Pattern,特殊格,Geng/Xin/Ren/Gui only,Day Branch is Chen/Wei/Xu/Chou specifically; valid combinations: Geng-Chen OR Xin-Wei OR Ren-Xu OR Gui-Chou,N/A,Day Pillar MUST match one of four canonical combinations exactly,Excessive Robbery without Officer control; Seal domination disrupting Day Master authority,Day Master authority + Officer/Seal control,Robbery/Peer competing; Seal overwhelming,High,三命通会/渊海子平,Canonical
27,拱禄格,Gong Lu Ge,Arching/Embracing Lu Pattern,特殊格,Any,Lu position NOT in Month Branch; Lu position "embraced" between Year and Hour branches; branches immediately before and after Lu in cycle both present,N/A,Day Master's Lu identified; Month Branch ≠ Lu; Year Branch = branch before Lu in cycle; Hour Branch = branch after Lu in cycle (or vice versa),Year and Hour branches cycle-embrace the DM's Lu position; Lu branch absent from Month,Month Branch disrupting the arch; contradicting branch positions,Embraced Lu function (similar to 建禄 but weaker),Disrupting branch,Medium,三命通会/渊海子平,Common
28,飞天禄马倒冲,Fei Tian Lu Ma Dao Chong,Flying Heaven Lu-Horse Reverse Clash,特殊格,Specific celestial stems required,Specific branch configurations producing celestial elevation,Celestial stem and horseback stem in specific flying configuration,Celestial stems and horseback stems in specific elevation configuration; clash reversed or inverted,Normal clash resolution prevented; flight interrupted; clash resolved normally instead of reversed,Celestial elevation effects + any supporting element,Earthly disruptions,Low,三命通会/神峰通考,Rare
29,两神成象,Liang Shen Cheng Xiang,Two-God Image Pattern,特殊格,Specific configurations,Specific combined elemental and stem-branch configurations,Two specific gods appearing in coordinated imagery,Two gods create combined symbolic image in elemental and branch reading; cultural/symbolic significance,Image disrupted; disharmony between the two gods,Both coordinated gods enhanced,Discord between the two gods,Very Low,三命通会/神峰通考,Rare
30,子辰双美格,Zi Chen Shuang Mei Ge,Child-Chen Dual Beauty Pattern,特殊格,Specific DM types,Year and Day branches specifically Zi and Chen (or vice versa) in water-favorable configuration,Rat and Dragon branches both present in specific positions,Year Pillar and Day Pillar contain Zi (Rat) and Chen (Dragon) creating water elemental resonance and dual-beauty symbolism,Beauty disrupted; conflicting branch positions; water element suppressed,Dual beauty symbolism enhancement; favorable outcomes through water resonance,Disruption of dual-beauty resonance,Very Low,三命通会/神峰通考,Rare
```

## Detection Priority Algorithm for Computational Implementation

The canonical sequence for structure detection must proceed in the following hierarchical order to avoid misclassification. The algorithm operates as a cascade: if a structure matches at a higher priority level, the analysis concludes at that level and does not proceed to lower-priority structures; only if no match occurs at a priority level does the algorithm advance to the next level.

**Priority Level 1: Rare Exotic Structures (魁罡, Flying Heaven, specialized celestial configurations)**
- Detection sequence: Check if Day Pillar matches the four 魁罡 combinations; check if celestial stems and horseback stems create flying configurations; check if symbolic two-god images or child-chen dual beauty configurations appear. Determinism: High to Very Low depending on specific structure.

**Priority Level 2: Transformation Patterns (化气格)**
- Detect whether two adjacent Heavenly Stems form one of the five canonical combinations (Jia-Ji → Earth, Yi-Geng → Metal, Bing-Xin → Water, Ding-Ren → Wood, Wu-Gui → Fire); verify that the Month Branch's Main Qi supports the transformation; confirm that no disrupting elements prevent the transformation from achieving true status (真化). Only if all conditions met, mark as transformation pattern and suspend analysis of Day Master's original element. Determinism: Low.

**Priority Level 3: Following Patterns (从格)**
- Assess Day Master strength through element count, rooting analysis, and support element presence. If Day Master is absolutely weak (no roots, no meaningful support), determine which element dominates the chart (Wealth, Officer, Output, or combined momentum). If genuine following conditions are met (dominated element is supported by Month Branch, no confounding elements, proper chain flow), classify

## Источники (live citations)
- [正八格包含八大类_新浪新闻](https://www.sina.cn/news/detail/5285129067171541.html)
- [BaZi Heavenly Stems (天干) Explained – Meanings in Four Pillars](https://www.skillon.com/bazi-feng-shui.cfm/topic/2743/bazi-heavenly-stems)
- [[PDF] Structures 格局](https://www.skillon.com/resources/Module%205%20-%20Structures%20-%20syllabus.pdf)
- [一篇看懂5大重點：天干五合定義、五行變化與合化實戰應用](https://habo.com.hk/%E5%A4%A9%E5%B9%B2%E4%BA%94%E5%90%88)
- [從格 - MASTERSO.COM 蘇民峰命理風水網站](https://www.masterso.com/classroom/classroom2_1_625.php)
- [074、飞天禄马倒冲格局 - YouTube](https://www.youtube.com/watch?v=tsnDDXJCfe4)
- [Hidden Heavenly Stems (藏干) in Earthly Branches - Imperial Harvest](https://imperialharvest.com/blog/hidden-heavenly-stems/)
- [How to Balance Your BaZi Element: A Practical Guide](https://novamastersconsulting.com/how-to-balance-your-bazi-element-a-practical-guide/)
- [地支详解：十二地支的奥秘 - 天机爻Wiki](https://wiki.tianjiyao.com/theory/earthly-branches.html)
- [Broken Structures In BaZi: 'Po Ge' (破格)](https://www.masterseanchan.com/blog/broken-structures-in-bazi/)
- [五行- 金曰从革，土爰稼穑。润下作咸，炎上作苦 - 尚书](https://shangshu.5000yan.com/zhoushu/hongfan/19270.html)
- [Complete Guide to BaZi Patterns: Zheng Ge, Zhuan Wang Ge, and ...](https://www.deeporacle.ai/en/bazi/blog/bazi-patterns-complete)
- [日主强弱——判断命盘的第一把钥匙](https://scryptomancer.com/books/wuxing-destiny/6)
- [地支合局的力量- 聚賢館文化有限公司Juxian Guan Ltd.](https://www.juxian.com.hk/r014/)
- [Traditional Chinese Children's Primers: A Sourcebook - jstor](https://www.jstor.org/content/pdf/oa_book_monograph/10.3998/mpub.13081893.pdf)
- [Bazi Hidden Stems (Cang Gan 藏干): Complete Guide](https://bazifortune.app/blog/bazi-hidden-stems-cang-gan-guide)
- [CN102006890A - 靶向脂质](https://patents.google.com/patent/CN102006890A/zh)
- [八字格局中的一气专旺格——润下格 - 神机阁](https://www.shenjige.cn/details/p8OB734l3.html)
- [BaZi Sample | PDF - Scribd](https://www.scribd.com/document/456515668/BaZi-Sample)
- [BaZi: SMTH - 弃命从财 Follow Wealth structure](http://treybazi.blogspot.com/2013/07/bazi-smth-follow-wealth-structure.html)
- [BaZi Calculator, Chinese Bazi Chart and Meaning](https://www.yourchineseastrology.com/calendar/bazi/)
- [十二地支藏干正确表](http://doc360.baidu.com/view/3c6c82b5b90d4a7302768e9951e79b8968026897.html)
- [奇門遁甲吉凶的二十八種格局 - 方格子](https://vocus.cc/article/64258120fd89780001289f9a)
- [What Is Follow The Leader Structure In Bazi](https://www.fengshuied.com/follow-the-leader-bazi)
- [https://huggingface.co/espnet/owsm_v3/commit/1baf5...](https://huggingface.co/espnet/owsm_v3/commit/1baf5040235c18fa44e7877759db429fe56a3bbb.diff?file=exp%2Fs2t_train_s2t_transformer_conv2d_size1024_e24_d24_lr2.5e-4_warmup10k_finetune_raw_bpe50000%2Fconfig.yaml)
- [[PDF] The Making of Universal Salvation Rites and Buddho-Daoist ...](https://dash.harvard.edu/server/api/core/bitstreams/ef57c38d-1409-40a4-a1ae-460bd12561a1/content)
- [Four Pillars of Destiny - Wikipedia](https://en.wikipedia.org/wiki/Four_Pillars_of_Destiny)
- [Decoding the Bazi Chart 丁卯 己酉 庚寅 甲申 - Lemon8-app](https://www.lemon8-app.com/@yizhitangsg/7559216850601542162?region=sg)
- [bazi/examples/guan.md at master · china-testing/bazi](https://github.com/china-testing/bazi/blob/master/examples/guan.md)
- [Can Bazi Help You Understand Love and Compatibility?](https://www.heyuu.com.au/blog/bazi-love-compatibility)
- [The original ZiPing - Classical BaZi and Contemporary ZWDS](http://treybazi.blogspot.com/2015/03/the-original-ziping.html)
- [Theoretical Basis of Day Master Strength and Weakness](https://www.oreateai.com/blog/methods-for-judging-the-strength-and-weakness-of-the-day-master-in-bazi-astrology-an-academic-discussion/633a7f50d0c9872ba2b3981e98b7caa6)
- [Understanding the '杀印相生' Pattern in Bazi: A Zi Ping Method Guide](https://www.lemon8-app.com/@wby184757l6/7545272771161358864?region=sg)
- [Is There A Difference Between Direct Wealth & Indirect Wealth?](https://www.masterseanchan.com/blog/difference-between-direct-wealth-indirect-wealth/)
- [Hurting Officer Case Study: An Elitist Who Ended Up Nowhere](https://www.masterseanchan.com/case-studies/bazi/hurting-officer-bazi-chart-who-ended-up-nowhere/)
- [The 12 Stages of Growth (十二长生) in Bazi - Imperial Harvest](https://imperialharvest.com/blog/the-12-stages-of-growth/)
- [The Ultimate 2026 Bazi Guide to Predicting Children: Master 5 Key ...](https://discoveringrncp.hk/en/%E5%85%AB%E5%AD%97%E7%9C%8B%E5%AD%90%E5%A5%B3)
- [The Ten Gods in BaZi: How Profiling Works In Chinese Metaphysics](https://www.masterseanchan.com/blog/ten-gods-bazi-profile-how-its-done/)
- [申子辰三合水Monkey-Rat-Dragon Water Trine — BaZi Branch ...](https://www.masterseanchan.com/bazi-shen-zi-chen-trine/)
- [第十八卷崇禎十五年壬午- 中國哲學書電子化計劃 - Chinese Text Project](https://ctext.org/wiki.pl?if=gb&chapter=426432&remap=gb)
- [BaZi: A Deeper Understanding of the Hidden Stems 藏干](https://www.skillon.com/bazi-feng-shui.cfm/topic/2742/bazi-a-deeper-understanding-of-the-hidden-stems)
- [Five Elements Guide - Complete Wood Fire Earth Metal Water Theory](https://www.fatemaster.ai/en/guides/wuxing)
- [Visible Particle Series Search Algorithm and Its Application in ... - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8838178/)
- [The 12 Earthly Branches (十二地支) - Imperial Harvest](https://imperialharvest.com/blog/12-earthly-branches/)
- [1 - Hugging Face](https://huggingface.co/openbmb/cpm-bee-1b/commit/bd72a61dd7a59086ed7456f1dfcaa995c8ec58a3.diff)
- [BaZi Calculator - Feng Shui in Motion](https://fsinmotion.com/bazi-calculator/)
- [Feng Shui Magazine June14 | PDF | Yin And Yang | Marriage - Scribd](https://www.scribd.com/document/483537845/Feng-Shui-Magazine-June14)
- [BaZi Classical Series | PDF | Yin And Yang | East Asia](https://www.scribd.com/document/317668091/BaZi-Classical-Series)
- [[PDF] The Five Elements' Influence on Different Types of Warfare - BaziChic](https://www.bazichic.com/uploads/documents/bazichik20230624164907.pdf)
- [Ba Zi Ge Ju Explained: Structure, Types, and Determination Methods](https://www.cantian.ai/wiki/other_words_explanations/geju/)

---

**Model:** perplexity/sonar-deep-research
**Tokens:** in=1984, out=16384, total=18368
