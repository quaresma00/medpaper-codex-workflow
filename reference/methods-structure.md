# Methods architecture for medical manuscripts

This guide controls structure and scope; it is not a mandatory template. Adapt headings to
the study design, reporting guideline, target journal, and what was actually done. The aim is
a compact main Methods section that lets a medical reader judge validity and interpret the
Results, with reproducibility detail moved to a supplement only when it is genuinely long.

## Default architecture

For an ordinary original clinical study, begin with roughly four to seven substantive
subsections. Merge adjacent topics when each would otherwise be only a short paragraph.

1. **Study design and setting** — design, sites, dates, oversight and ethics when concise.
2. **Participants and data source** — recruitment or sampling, eligibility, exclusions and
   follow-up; name the data source here rather than creating a decorative heading for it.
3. **Design-specific procedures and measurements** — intervention and randomization,
   exposure, index/reference tests, specimen or laboratory methods, or qualitative data
   collection, as applicable.
4. **Outcomes and other variables** — primary and secondary outcomes, ascertainment,
   definitions, covariates and relevant blinding.
5. **Statistical analysis** — analysis populations, primary model, uncertainty, missing data,
   multiplicity and prespecified secondary/sensitivity work in a coherent sequence.

`Statistical analysis` should normally be the last subsection of a quantitative paper.
Use `Data analysis` for qualitative studies and `Evidence synthesis` (or the journal's
equivalent) for systematic reviews. A reporting checklist is a completeness audit, not an
instruction to turn every item into a heading.

Do not automatically append standalone `Sensitivity analyses`, `Subgroup analyses`,
`Missing data`, `Software`, or `Ethics` subsections after the analysis subsection. State these
inside the most relevant subsection when brief. A separate heading is justified only when
the topic is central, complex, and consistent with the target journal's current examples.

## Design-specific adaptations

- **Randomized trial:** design and oversight; participants; randomization/intervention and
  procedures; outcomes; statistical analysis.
- **Observational cohort or case-control study:** design/setting; participants and data;
  exposures, outcomes and covariates; statistical analysis.
- **Diagnostic-accuracy study:** design/participants; index test and reference standard,
  including thresholds and blinding; statistical analysis.
- **Prediction or prognostic model:** data/participants; outcome and candidate predictors;
  model development/validation and performance. Keep the main account readable; extensive
  preprocessing, tuning, resampling and model specifications usually belong in a supplement.
- **Systematic review or meta-analysis:** protocol/eligibility; information sources and
  search; selection/data extraction/risk of bias; evidence synthesis or meta-analysis.
- **Qualitative study:** design/framework/setting; sampling and participants; data collection;
  data analysis, with reflexivity or trustworthiness where material.

These are routes through the same logic, not six compulsory templates. Use the terminology
expected for the actual design and omit inapplicable topics.

## Main Methods versus supplementary Methods

Keep in the main Methods every fact needed to understand internal validity and the primary
Results: core design and setting, eligibility, primary intervention/exposure/index test,
primary outcome definitions, primary analysis population and model, and essential handling
of bias, missingness or multiplicity.

Create `07_manuscript/supplementary_methods.md` only when necessary. Good candidates include
complete database search strings, long diagnosis/procedure code lists, full laboratory or
assay protocols, algorithm pseudocode, tuning grids, full imputation models, extended
sensitivity specifications, long subgroup definitions, questionnaires/interview guides, and
a full statistical analysis plan. Refer to the supplement once at the relevant point in the
main Methods. Do not duplicate paragraphs across both files, and never use the supplement to
hide a primary design or analysis choice.

## Structural evidence from published designs

The architecture above was derived by comparing full-text Methods organization across
different medical study designs (checked 2026-09-04):

- The RECOVERY randomized trial progresses from trial design/oversight through randomization,
  procedures and outcomes to statistical analysis: [RECOVERY Collaborative Group, *New
  England Journal of Medicine*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7383595/).
- A multicentre retrospective cohort uses study design/participants, data collection,
  laboratory procedures and definitions before statistical analysis: [Zhou et al., *The
  Lancet*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7270627/).
- A diagnostic-accuracy study separates design/participants, eligibility and test methods,
  including index and reference standards, before data management/statistical analysis:
  [TrueNat MTB Plus study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12721543/).
- A qualitative study uses design/setting, participants/recruitment, data collection, and data
  analysis/management: [Davis et al., *PLOS ONE*](https://pmc.ncbi.nlm.nih.gov/articles/PMC10246844/).
- A systematic review reports sources/search, eligibility, selection/extraction, risk of bias
  and synthesis without manufacturing a subsection for every checklist item: [Wynants et al.,
  *BMJ*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7222643/).
- Prediction-model guidance shows why design-specific implementation detail can become long
  enough for a supplement while primary choices remain visible in the main Methods:
  [Efthimiou et al., step-by-step clinical prediction modelling guide](https://pmc.ncbi.nlm.nih.gov/articles/PMC11369751/).

The recurring pattern is a reader-facing sequence ending in the analysis approach, while the
number and names of earlier subsections change with design. That pattern—not a rigid list—is
the workflow default.
