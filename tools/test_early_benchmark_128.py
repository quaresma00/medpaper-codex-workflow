"""Synthetic recent-paper/early-science review contracts, never real publication evidence."""
import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_benchmark_acceptance as fixture
from wfcore import benchmark as b,earlyreview as er
from wfcore.packagefreeze import _sha256
from wfcore.readiness import atomic_json
from wfcore.state import State


class RecentBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.BenchmarkTests("runTest");self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.project=self.base.project;self.doc=self.base.doc
        # Construct a NEW synthetic fixture plan; do not change a real project's lock.
        (self.project/".wf/benchmark_science_lock.json").unlink()
        library=b.load(self.project,"06_refs/library.json")
        manifest=b.load(self.project,"06_refs/fulltext/retrieval_manifest.json")
        template=copy.deepcopy(self.doc["comparators"][0])
        original=(self.project/template["fulltext"]).read_text(encoding="utf-8")
        for i in range(3,6):
            key=f"test{i}";pmid=str(90000000+i);rel=f"06_refs/fulltext/{key}.xml"
            self.base.text(rel,original.replace("90000001",pmid))
            row=copy.deepcopy(template);row.update(citekey=key,fulltext=rel,sha256=_sha256(self.project/rel))
            self.doc["comparators"].append(row)
            library["entries"].append({"citekey":key,"pmid":pmid,"year":"2026"})
            manifest["retrievals"].append({"citekey":key,"pmid":pmid,"fulltext":rel,"access":"oa","sha256":_sha256(self.project/rel)})
        today=datetime.now(timezone.utc).date()
        self.search="06_refs/cache/esearch_pubmed_synthetic_recent.json"
        self.base.data(self.search,{"esearchresult":{"querytranslation":"synthetic recent comparison","idlist":[r["pmid"] for r in library["entries"]],"count":"5"}})
        self.doc["comparator_selection"]={"version":1,"searched_at":str(today),"period_start":str(today-timedelta(days=730)),
           "selection_basis":"Synthetic matched design and clinical comparison fixtures, not an actual medical search.",
           "searches":[{"query":"synthetic recent comparison","translation":"synthetic recent comparison","cache_file":self.search,"sha256":_sha256(self.project/self.search)}]}
        for entry in library["entries"]:entry["year"]=str(today.year)
        for row in self.doc["comparators"]:
            row["published_at"]=str(today-timedelta(days=14))
            rel=row["fulltext"]
            text=(self.project/rel).read_text(encoding="utf-8").replace("</body>","<p>Figure 1. Synthetic primary finding. Figure 2. Synthetic comparison.</p></body>")
            self.base.text(rel,text);row["sha256"]=_sha256(self.project/rel)
            record=next(r for r in manifest["retrievals"] if r["citekey"]==row["citekey"]);record["sha256"]=row["sha256"]
            obs=row["observations"];obs.update(main_figures=2,main_tables=1,supp_figures=0,supp_tables=0)
            obs["display_inventory"]=[{"id":name,"kind":kind,"type":"Synthetic controlled clinical display specimen",
                "clinical_role":"Identifies the real question that this synthetic display would answer.",
                "analysis_shown":"Shows the declared comparison and interval as an inspectable fixture.","locator":"Synthetic caption in article body"}
                for name,kind in (("Figure 1","main_figure"),("Figure 2","main_figure"),("Table 1","main_table"))]
        self.doc["adaptation"]["displays"]["count_comparison"]={"planned_main_figures":1,"comparator_median_main_figures":2,
            "scientific_reason":"This synthetic project has one valid primary comparison rather than the two distinct study populations in comparator fixtures; its necessary reader tasks remain represented in the declared plan."}
        self.base.data("06_refs/library.json",library);self.base.data("06_refs/fulltext/retrieval_manifest.json",manifest)
        self.base.write_doc();b.seal(self.project)

    def errors(self):return b.verify_benchmark(self.project)
    def save(self):self.base.write_doc()

    def test_five_recent_fulltexts_actual_inventories_and_departure_pass(self):
        self.assertEqual(self.errors(),[])
        self.assertEqual(len(self.doc["comparators"]),5)

    def test_two_old_comparators_cannot_be_called_recent_complete(self):
        self.doc["comparators"]=self.doc["comparators"][:2]
        for row in self.doc["comparators"]:row["published_at"]="2010-01-01"
        self.save();errors=" ".join(self.errors())
        self.assertIn("5–10",errors);self.assertIn("publication",errors)

    def test_actual_search_response_cannot_be_replaced_by_a_boolean(self):
        self.doc["comparator_selection"]["searches"]=[];self.doc["comparator_selection"]["search_complete"]=True
        self.save();self.assertTrue(any("raw search response" in e for e in self.errors()))

    def test_search_translation_and_source_bytes_are_bound(self):
        self.base.data(self.search,{"esearchresult":{"querytranslation":"changed unrelated search","idlist":[],"count":"0"}})
        self.assertTrue(any("absent or changed" in e for e in self.errors()))

    def test_claimed_figure_inventory_must_match_actual_counts_and_captions(self):
        self.doc["comparators"][0]["observations"]["display_inventory"][0]["id"]="Figure 99"
        self.doc["comparators"][1]["observations"]["main_figures"]=6
        self.save();errors=" ".join(self.errors())
        self.assertIn("Figure 99 is absent",errors);self.assertIn("inventory must match",errors)

    def test_fewer_planned_figures_needs_current_actual_count_comparison(self):
        self.doc["adaptation"]["displays"]["count_comparison"]={"scientific_reason":"A focused paper is enough."}
        self.save();self.assertTrue(any("fewer than recent comparators" in e for e in self.errors()))

    def test_sealed_selection_cannot_silently_lower_pool_floor(self):
        self.doc["adaptation"]["references"]["library_floor"]=3
        self.save();errors=" ".join(self.errors())
        self.assertIn("do not autonomously reduce",errors);self.assertIn("plan changed",errors)

    def test_pool_floor_is_checked_after_discovery_not_per_methods_section(self):
        self.assertTrue(any("minimum45" in e for e in b.coverage(self.project,library_only=True)))
        self.assertEqual(b.coverage(self.project,section="methods",library_only=True),[])

    def test_lowering_project_configuration_cannot_reduce_the_sealed_pool_floor(self):
        self.base.state.set_config("reflib_min","60");b.seal(self.project)
        self.base.state.set_config("reflib_min","45")
        self.assertTrue(any("minimum60" in e for e in b.coverage(self.project,library_only=True)))
        with self.assertRaisesRegex(ValueError,"Do not lower the sealed"):b.seal(self.project)

    def test_external_fulltext_keeps_actual_route_and_identity(self):
        manifest=b.load(self.project,"06_refs/fulltext/retrieval_manifest.json")
        manifest["retrievals"][0].update(access="external",authorization_note="User explicitly selected this external route for the actual paper fixture.")
        self.base.data("06_refs/fulltext/retrieval_manifest.json",manifest)
        self.assertEqual(self.errors(),[])

    def test_legacy_two_article_plan_keeps_historical_requirements(self):
        for row in self.doc["comparators"]:row.pop("published_at",None)
        self.doc.pop("comparator_selection");self.doc["comparators"]=self.doc["comparators"][:2]
        self.save();self.assertEqual(b.verify_benchmark(self.project,require_lock=False),[])


class EarlyScientificReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="medpaper-early-review-");self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name);self.state=State(self.project).create("medpaper","1.28.0",er.OWNER)
        for rel in ("01_protocol/protocol_final.md","07_manuscript/methods.md","07_manuscript/results.md",
                    "05_figures/legends.md","04_tables/table_captions.md","03_analysis/code/analyse.R"):
            self.text(rel,"Synthetic source specimen for early review. No real study or approval is represented.")
        for rel in ("01_protocol/analysis_contract.json","01_protocol/study_facts.json","03_analysis/results/main.json"):
            atomic_json(self.project/rel,{"fixture":"synthetic"})
        self.text("05_figures/out/Figure1.svg","<svg><text>Synthetic clinical display</text></svg>")
        atomic_json(self.project/"01_protocol/artifact_plan.json",{"main_figures":[{"id":"Figure 1","file":"05_figures/out/Figure1.svg"}],"main_tables":[],"supp_figures":[],"supp_tables":[]})
        self.text("01_protocol/artifact_benchmark.md",'# Benchmark\n```json\n{"benchmark_version":1,"comparators":[]}\n```\n')

    def text(self,rel,value):
        path=self.project/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path

    def report(self,record,verdict="GO",agent="/root/science_reviewer"):
        observations={title:"This synthetic independent review inspected the actual specified sources and distinguishes a supported medical inference from unsupported design claims." for title in er.HEADINGS}
        meta={"early_review_version":1,"review_id":record["id"],"reviewed_artifacts":record["reviewed_artifacts"],
              "reviewer":{"role":"independent_subagent","agent_id":agent},"verdict":verdict,
              "article_type":"original_article","marginal_analysis_value":"low","finding_inventory_complete":True,
              "findings":[],"section_verdicts":{title:"no_actionable_findings" for title in er.HEADINGS}}
        if verdict=="REVISE":
            meta["findings"]=[{"id":"D1","section":"Methods and validity","text":"The synthetic time origin needs correction before drawing the proposed inference.","locator":"Methods, study population","category":"objective","affects_science":True}]
            meta["section_verdicts"]["Methods and validity"]="findings_listed"
            observations["Methods and validity"]+=" [finding:D1] The declared time origin does not correspond to follow-up."
        text="\n\n".join("## "+title+"\n\n"+observations[title] for title in er.HEADINGS)+"\n```json\n"+json.dumps(meta)+"\n```\n"
        return self.text(record["report_destination"],text)

    def test_review_happens_without_abstract_or_full_manuscript(self):
        record=er.start(self.project,"/root");path=self.report(record);er.attach(self.project,path)
        self.assertEqual(er.verify(self.project),[])
        self.assertNotIn("07_manuscript/abstract.md",record["reviewed_artifacts"])
        self.assertNotIn("07_manuscript/full_manuscript.md",record["reviewed_artifacts"])

    def test_unchanged_review_is_reused_without_new_agent_round(self):
        record=er.start(self.project,"/root");er.attach(self.project,self.report(record))
        before=(self.project/er.RECORD).read_bytes()
        self.assertEqual(er.start(self.project,"/root")["id"],"E001")
        self.assertEqual((self.project/er.RECORD).read_bytes(),before)

    def test_no_go_or_low_yield_reports_hold_before_more_writing(self):
        record=er.start(self.project,"/root");er.attach(self.project,self.report(record,"NO_GO"))
        error=" ".join(er.verify(self.project));self.assertIn("notify the author now",error)
        self.assertIn("Do not draft Abstract",error)

    def test_revise_report_has_located_owner_issues_and_blocks_advance(self):
        record=er.start(self.project,"/root");er.attach(self.project,self.report(record,"REVISE"))
        self.assertTrue(any("REVISE" in e for e in er.verify(self.project)))
        self.assertEqual(self.state.current,er.OWNER)

    def test_executor_cannot_impersonate_independent_reviewer(self):
        record=er.start(self.project,"/root")
        with self.assertRaisesRegex(ValueError,"actual independent"):
            er.attach(self.project,self.report(record,agent="/root"))
        self.assertIsNone(er.load(self.project,er.RECORD)["report"])

    def test_missing_executor_identity_is_not_invented(self):
        with self.assertRaisesRegex(ValueError,"actual executor"):er.start(self.project,None)

    def test_invalid_reviewer_identity_is_a_clear_pending_review(self):
        record=er.start(self.project,"/root")
        for agent in (None,42,""):
            with self.assertRaisesRegex(ValueError,"actual independent"):
                er.attach(self.project,self.report(record,agent=agent))

    def test_result_change_requires_scoped_current_scientific_reading(self):
        record=er.start(self.project,"/root");er.attach(self.project,self.report(record))
        atomic_json(self.project/"03_analysis/results/main.json",{"fixture":"genuinely changed scientific input"})
        self.assertTrue(any("stale" in e for e in er.verify(self.project)))
        renewed=er.start(self.project,"/root")
        self.assertEqual(renewed["id"],"E002")
        self.assertEqual(renewed["changed_since_previous"],["03_analysis/results/main.json"])

    def test_source_changes_during_reading_do_not_get_certified(self):
        record=er.start(self.project,"/root");path=self.report(record)
        self.text("07_manuscript/methods.md","Changed method text during the review; this is a synthetic integrity defect.")
        with self.assertRaisesRegex(ValueError,"changed during reading"):er.attach(self.project,path)

    def test_later_discussion_notes_and_abstract_claim_bindings_do_not_reopen_science(self):
        record=er.start(self.project,"/root");er.attach(self.project,self.report(record))
        self.text("03_analysis/notes.md","## Discussion points\nLater writing-only comparison notes.")
        atomic_json(self.project/"07_manuscript/claim_bindings.json",{"claims":[{"section":"Abstract","value":"synthetic new writing binding"}]})
        self.text("07_manuscript/abstract.md","A subsequently drafted synthetic abstract.")
        self.assertEqual(er.verify(self.project),[])

    def test_later_citation_passages_reuse_review_but_changed_benchmark_plan_does_not(self):
        record=er.start(self.project,"/root");er.attach(self.project,self.report(record))
        doc=b.dossier(self.project)
        doc["adaptation"]={"structure":{"methods":"A newly changed scientific design requiring actual independent reading."},"references":{"roles":[]}}
        self.text(b.SCIENCE,"# Benchmark\n```json\n"+json.dumps(doc)+"\n```\n")
        # Adding a previously absent protected structure is a real plan change.
        self.assertTrue(any("stale" in e for e in er.verify(self.project)))
        # Prepare a new valid scientific version, then only add writing mappings.
        role={"id":"prior","section":"discussion","claim":"Existing clinical question comparison.","source_type":"primary","required":True}
        doc["adaptation"]["references"]["roles"]=[role]
        self.text(b.SCIENCE,"# Benchmark\n```json\n"+json.dumps(doc)+"\n```\n")
        renewed=er.start(self.project,"/root");er.attach(self.project,self.report(renewed))
        role.update(citekeys=["existing"],passage="The later Discussion compares actual prior observations [@existing].")
        self.text(b.SCIENCE,"# Benchmark\n```json\n"+json.dumps(doc)+"\n```\n")
        self.assertEqual(er.verify(self.project),[])
        self.assertEqual(er.start(self.project,"/root")["id"],renewed["id"])

    def test_claimed_go_with_unresolved_objective_finding_is_rejected(self):
        record=er.start(self.project,"/root");path=self.report(record,"REVISE")
        path.write_text(path.read_text(encoding="utf-8").replace('"verdict": "REVISE"','"verdict": "GO"'),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"cannot conceal"):er.attach(self.project,path)

    def test_actual_pdf_reading_preview_is_bound_not_guessed_from_filename(self):
        preview=self.text(".wf/display_previews/Figure1.png","Actual synthetic rendering bytes for input identity test.")
        atomic_json(self.project/"01_protocol/display_review.json",{"final_reviews":{"Figure 1":{
            "reviewed_file":"05_figures/out/Figure1.svg","rendered_preview":".wf/display_previews/Figure1.png","rendered_sha256":_sha256(preview)}}})
        record=er.start(self.project,"/root");self.assertIn(".wf/display_previews/Figure1.png",record["reviewed_artifacts"])
        preview.write_text("Changed actual preview.",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"preview is missing/stale"):er.inputs(self.project)

    def test_preabstract_scoped_repair_does_not_require_future_manuscript(self):
        from wfcore import registry,revision
        pipe=registry.load()
        source="07_manuscript/results.md"
        row={"schema_version":2,"round_id":"R001","status":"active","review_stage":er.OWNER,
             "baseline":revision.snapshot(self.project),"items":[{"kind":"results-text","change_type":"wording",
                 "owning_stage":"S09_results","affected_sources":[source]}]}
        before=json.loads(json.dumps(self.state.data["stages"]))
        revision.plan_scope(self.project,pipe,row)
        self.assertEqual(self.state.current,er.OWNER);self.assertEqual(before,self.state.data["stages"])
        self.assertFalse(any(check["stage"]=="S17_assemble" for check in row["checks"]))
        self.assertNotIn("07_manuscript/abstract.md",row["rebuild_files"])
        self.assertNotIn("07_manuscript/full_manuscript.md",row["rebuild_files"])

    def test_completed_legacy_project_has_no_backfilled_early_audit(self):
        self.state.data["engine_pin"]="1.27.0";self.state.save()
        self.assertEqual(er.verify(self.project),[])


if __name__=="__main__":unittest.main(verbosity=2)
