"""3D CodeBalance Visualizer — generates a self-contained HTML report.

Runs CodeBalance on a set of Java functions and produces an interactive
3D scatter plot (Energy vs Debt vs Safety) using pure HTML + JavaScript
(no plotly dependency required).

Usage:
    # Score PetClinic functions embedded in this script
    python3 scripts/visualize_codebalance.py

    # Or score from a results CSV produced by run_ablation.py
    python3 scripts/visualize_codebalance.py --csv results/ablation_results.csv

Output:
    results/codebalance_3d.html  — self-contained interactive HTML
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from legacylens.analysis.codebalance import score_code

# ---------------------------------------------------------------------------
# Spring PetClinic corpus (13 functions)
# ---------------------------------------------------------------------------

SAMPLE_FUNCTIONS = [
    {
        "name": "initCreationForm",
        "category": "Simple View",
        "code": """
    @GetMapping("/owners/new")
    public String initCreationForm(Map<String, Object> model) {
        Owner owner = new Owner();
        model.put("owner", owner);
        return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
    }""",
    },
    {
        "name": "processCreationForm",
        "category": "Data Entry",
        "code": """
    @PostMapping("/pets/new")
    public String processCreationForm(Owner owner, @Valid Pet pet, BindingResult result, ModelMap model) {
        if (StringUtils.hasLength(pet.getName()) && pet.isNew() && owner.getPet(pet.getName(), true) != null) {
            result.rejectValue("name", "duplicate", "already exists");
        }
        owner.addPet(pet);
        if (result.hasErrors()) {
            model.put("pet", pet);
            return VIEWS_PETS_CREATE_OR_UPDATE_FORM;
        }
        this.owners.save(owner);
        return "redirect:/owners/" + owner.getId();
    }""",
    },
    {
        "name": "processNewVisitForm",
        "category": "Nested Logic",
        "code": """
    @PostMapping("/owners/{ownerId}/pets/{petId}/visits/new")
    public String processNewVisitForm(@Valid Visit visit, BindingResult result) {
        if (result.hasErrors()) {
            return "pets/createOrUpdateVisitForm";
        }
        this.visits.save(visit);
        return "redirect:/owners/{ownerId}";
    }""",
    },
    {
        "name": "triggerException",
        "category": "Error Handling",
        "code": """
    @GetMapping("/oups")
    public String triggerException() {
        throw new RuntimeException(
                "Expected: controller used to showcase what " + "happens when an exception is thrown");
    }""",
    },
    {
        "name": "processFindForm",
        "category": "Complex Data Flow",
        "code": """
    @GetMapping("/owners")
    public String processFindForm(@RequestParam(defaultValue = "1") int page, Owner owner,
            BindingResult result, Model model) {
        String lastName = owner.getLastName();
        if (lastName == null) { lastName = ""; }
        Page<Owner> ownersResults = findPaginatedForOwnersLastName(page, lastName);
        if (ownersResults.isEmpty()) {
            result.rejectValue("lastName", "notFound", "not found");
            return "owners/findOwners";
        }
        if (ownersResults.getTotalElements() == 1) {
            owner = ownersResults.iterator().next();
            return "redirect:/owners/" + owner.getId();
        }
        return addPaginationModel(page, model, ownersResults);
    }""",
    },
    {
        "name": "processUpdateOwnerForm",
        "category": "Update — ID Validation",
        "code": """
    @PostMapping("/owners/{ownerId}/edit")
    public String processUpdateOwnerForm(@Valid Owner owner, BindingResult result,
            @PathVariable("ownerId") int ownerId, RedirectAttributes redirectAttributes) {
        if (result.hasErrors()) {
            redirectAttributes.addFlashAttribute("error", "There was an error in updating the owner.");
            return VIEWS_OWNER_CREATE_OR_UPDATE_FORM;
        }
        if (!Objects.equals(owner.getId(), ownerId)) {
            result.rejectValue("id", "mismatch", "The owner ID in the form does not match the URL.");
            redirectAttributes.addFlashAttribute("error", "Owner ID mismatch. Please try again.");
            return "redirect:/owners/{ownerId}/edit";
        }
        owner.setId(ownerId);
        this.owners.save(owner);
        redirectAttributes.addFlashAttribute("message", "Owner Values Updated");
        return "redirect:/owners/{ownerId}";
    }""",
    },
    {
        "name": "showOwner",
        "category": "Detail View",
        "code": """
    @GetMapping("/owners/{ownerId}")
    public ModelAndView showOwner(@PathVariable("ownerId") int ownerId) {
        ModelAndView mav = new ModelAndView("owners/ownerDetails");
        Optional<Owner> optionalOwner = this.owners.findById(ownerId);
        Owner owner = optionalOwner.orElseThrow(() -> new IllegalArgumentException(
                "Owner not found with id: " + ownerId + ". Please ensure the ID is correct "));
        mav.addObject(owner);
        return mav;
    }""",
    },
    {
        "name": "Pet.processUpdateForm",
        "category": "Update — Name/Date Validation",
        "code": """
    @PostMapping("/pets/{petId}/edit")
    public String processUpdateForm(Owner owner, @Valid Pet pet, BindingResult result,
            RedirectAttributes redirectAttributes) {
        String petName = pet.getName();
        if (StringUtils.hasText(petName)) {
            Pet existingPet = owner.getPet(petName, false);
            if (existingPet != null && !Objects.equals(existingPet.getId(), pet.getId())) {
                result.rejectValue("name", "duplicate", "already exists");
            }
        }
        LocalDate currentDate = LocalDate.now();
        if (pet.getBirthDate() != null && pet.getBirthDate().isAfter(currentDate)) {
            result.rejectValue("birthDate", "typeMismatch.birthDate");
        }
        if (result.hasErrors()) { return VIEWS_PETS_CREATE_OR_UPDATE_FORM; }
        updatePetDetails(owner, pet);
        redirectAttributes.addFlashAttribute("message", "Pet details has been edited");
        return "redirect:/owners/{ownerId}";
    }""",
    },
    {
        "name": "showVetList",
        "category": "Paginated View",
        "code": """
    @GetMapping("/vets.html")
    public String showVetList(@RequestParam(defaultValue = "1") int page, Model model) {
        Vets vets = new Vets();
        Page<Vet> paginated = findPaginated(page);
        vets.getVetList().addAll(paginated.toList());
        return addPaginationModel(page, paginated, model);
    }""",
    },
    {
        "name": "showResourcesVetList",
        "category": "REST Endpoint",
        "code": """
    @GetMapping({ "/vets" })
    public @ResponseBody Vets showResourcesVetList() {
        Vets vets = new Vets();
        vets.getVetList().addAll(this.vetRepository.findAll());
        return vets;
    }""",
    },
    {
        "name": "Owner.addVisit",
        "category": "Domain Logic",
        "code": """
    public void addVisit(Integer petId, Visit visit) {
        Assert.notNull(petId, "Pet identifier must not be null!");
        Assert.notNull(visit, "Visit must not be null!");
        Pet pet = getPet(petId);
        Assert.notNull(pet, "Invalid Pet identifier!");
        pet.addVisit(visit);
    }""",
    },
    {
        "name": "Owner.getPet",
        "category": "Domain Logic",
        "code": """
    public Pet getPet(String name, boolean ignoreNew) {
        for (Pet pet : getPets()) {
            String compName = pet.getName();
            if (compName != null && compName.equalsIgnoreCase(name)) {
                if (!ignoreNew || !pet.isNew()) {
                    return pet;
                }
            }
        }
        return null;
    }""",
    },
    {
        "name": "Owner.addPet",
        "category": "Domain Logic",
        "code": """
    public void addPet(Pet pet) {
        if (pet.isNew()) {
            getPets().add(pet);
        }
    }""",
    },
]

# ---------------------------------------------------------------------------
# Apache Ant-style legacy corpus (12 functions) — for second plot
# ---------------------------------------------------------------------------

ANT_FUNCTIONS = [
    {
        "name": "execute",
        "category": "Build Task",
        "code": """
    public void execute() throws BuildException {
        if (srcdir == null) {
            throw new BuildException("srcdir attribute must be set", getLocation());
        }
        String[] files = srcdir.list();
        for (String file : files) {
            if (file.endsWith(".java")) {
                compileFile(new File(srcdir, file));
            }
        }
    }""",
    },
    {
        "name": "compileFile",
        "category": "File Processing",
        "code": """
    private void compileFile(File sourceFile) throws BuildException {
        FileInputStream fis = null;
        try {
            fis = new FileInputStream(sourceFile);
            byte[] buffer = new byte[1024];
            int bytesRead;
            while ((bytesRead = fis.read(buffer)) != -1) {
                outputStream.write(buffer, 0, bytesRead);
            }
        } catch (Exception e) {
            throw new BuildException("Compilation failed for: " + sourceFile.getName());
        } finally {
            if (fis != null) {
                try { fis.close(); } catch (Exception ignore) {}
            }
        }
    }""",
    },
    {
        "name": "log",
        "category": "Logging",
        "code": """
    protected void log(String message) {
        String timestamp = new java.text.SimpleDateFormat("HH:mm:ss").format(new java.util.Date());
        System.out.println("[" + timestamp + "] " + message);
    }""",
    },
    {
        "name": "copyFiles",
        "category": "File Processing",
        "code": """
    private void copyFiles(File src, File dest) throws BuildException {
        if (!dest.exists()) { dest.mkdirs(); }
        String[] files = src.list();
        if (files == null) return;
        for (String file : files) {
            File srcFile = new File(src, file);
            File destFile = new File(dest, file);
            if (srcFile.isDirectory()) {
                copyFiles(srcFile, destFile);
            } else {
                copyBytes(srcFile, destFile);
            }
        }
    }""",
    },
    {
        "name": "copyBytes",
        "category": "File Processing",
        "code": """
    private void copyBytes(File src, File dest) throws BuildException {
        FileInputStream in = null;
        FileOutputStream out = null;
        try {
            in = new FileInputStream(src);
            out = new FileOutputStream(dest);
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) >= 0) {
                out.write(buf, 0, n);
            }
        } catch (Exception e) {
            throw new BuildException("Copy failed: " + e.getMessage());
        } finally {
            try { if (in != null) in.close(); } catch (Exception ignore) {}
            try { if (out != null) out.close(); } catch (Exception ignore) {}
        }
    }""",
    },
    {
        "name": "deleteDir",
        "category": "File System",
        "code": """
    private boolean deleteDir(File dir) {
        if (dir.isDirectory()) {
            String[] children = dir.list();
            for (int i = 0; i < children.length; i++) {
                boolean success = deleteDir(new File(dir, children[i]));
                if (!success) return false;
            }
        }
        return dir.delete();
    }""",
    },
    {
        "name": "runCommand",
        "category": "Shell Execution",
        "code": """
    private int runCommand(String command) throws BuildException {
        try {
            Process proc = Runtime.getRuntime().exec(command);
            proc.waitFor();
            return proc.exitValue();
        } catch (Exception e) {
            throw new BuildException("Command failed: " + command + " - " + e.getMessage());
        }
    }""",
    },
    {
        "name": "parseProperties",
        "category": "Configuration",
        "code": """
    private Properties parseProperties(File propFile) {
        Properties props = new Properties();
        try {
            FileInputStream fis = new FileInputStream(propFile);
            props.load(fis);
            fis.close();
        } catch (Exception e) {
            log("Warning: could not load " + propFile.getName());
        }
        return props;
    }""",
    },
    {
        "name": "buildClasspath",
        "category": "Build Config",
        "code": """
    private String buildClasspath(List<File> jars) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < jars.size(); i++) {
            if (i > 0) sb.append(File.pathSeparator);
            sb.append(jars.get(i).getAbsolutePath());
        }
        return sb.toString();
    }""",
    },
    {
        "name": "validateConfig",
        "category": "Validation",
        "code": """
    private void validateConfig() throws BuildException {
        if (srcdir == null || !srcdir.exists()) {
            throw new BuildException("srcdir must exist: " + srcdir);
        }
        if (destdir == null) {
            throw new BuildException("destdir attribute must be set");
        }
        if (!destdir.exists()) { destdir.mkdirs(); }
        if (classpath == null || classpath.isEmpty()) {
            log("Warning: no classpath set - using JVM defaults");
        }
    }""",
    },
    {
        "name": "writeReport",
        "category": "Reporting",
        "code": """
    private void writeReport(String report, File outFile) throws BuildException {
        try {
            java.io.FileWriter fw = new java.io.FileWriter(outFile, true);
            fw.write(report);
            fw.write(System.getProperty("line.separator"));
            fw.close();
        } catch (Exception e) {
            throw new BuildException("Failed to write report: " + e.getMessage());
        }
    }""",
    },
    {
        "name": "findFiles",
        "category": "File System",
        "code": """
    private List<File> findFiles(File dir, String extension) {
        List<File> result = new ArrayList<File>();
        if (!dir.isDirectory()) return result;
        for (File f : dir.listFiles()) {
            if (f.isDirectory()) {
                result.addAll(findFiles(f, extension));
            } else if (f.getName().endsWith(extension)) {
                result.add(f);
            }
        }
        return result;
    }""",
    },
]

CORPORA = {
    "petclinic": {
        "label": "Spring PetClinic",
        "functions": SAMPLE_FUNCTIONS,
        "output": "codebalance_3d_petclinic.html",
    },
    "ant": {
        "label": "Apache Ant-style Legacy",
        "functions": ANT_FUNCTIONS,
        "output": "codebalance_3d_ant.html",
    },
}

# ---------------------------------------------------------------------------
# HTML template — self-contained 3D scatter with Three.js-style via CSS transforms
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LegacyLens — CodeBalance 3D Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; }}
  header {{ padding: 2rem; border-bottom: 1px solid #1e293b; }}
  header h1 {{ font-size: 1.8rem; color: #7dd3fc; letter-spacing: -0.5px; }}
  header p {{ color: #64748b; margin-top: 0.25rem; font-size: 0.9rem; }}
  .container {{ display: flex; gap: 2rem; padding: 2rem; max-width: 1400px; margin: 0 auto; flex-wrap: wrap; }}
  .chart-wrap {{ flex: 1 1 600px; background: #1e293b; border-radius: 12px; padding: 1.5rem; }}
  .chart-wrap h2 {{ font-size: 1rem; color: #94a3b8; margin-bottom: 1rem; }}
  canvas {{ width: 100% !important; border-radius: 8px; }}
  .table-wrap {{ flex: 1 1 400px; background: #1e293b; border-radius: 12px; padding: 1.5rem; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ text-align: left; padding: 0.5rem 0.75rem; color: #7dd3fc; border-bottom: 1px solid #334155; }}
  td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #0f172a; }}
  .grade {{ font-weight: 700; }}
  .grade-A {{ color: #4ade80; }} .grade-B {{ color: #86efac; }}
  .grade-C {{ color: #fde68a; }} .grade-D {{ color: #fb923c; }} .grade-F {{ color: #f87171; }}
  .bar {{ display: inline-block; height: 8px; border-radius: 4px; vertical-align: middle; margin-left: 4px; }}
  .energy-bar {{ background: #38bdf8; }} .debt-bar {{ background: #a78bfa; }} .safety-bar {{ background: #f87171; }}
  .legend {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }}
  .legend-item {{ display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: #94a3b8; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  footer {{ text-align: center; color: #334155; padding: 1rem; font-size: 0.75rem; }}
  .summary-cards {{ display: flex; gap: 1rem; flex-wrap: wrap; padding: 0 2rem; max-width: 1400px; margin: 0 auto 1rem; }}
  .card {{ flex: 1 1 150px; background: #1e293b; border-radius: 10px; padding: 1rem 1.25rem; }}
  .card .val {{ font-size: 2rem; font-weight: 700; color: #7dd3fc; }}
  .card .lbl {{ font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; }}
</style>
</head>
<body>
<header>
  <h1>🔭 LegacyLens — CodeBalance 3D Report</h1>
  <p>Generated {timestamp} &nbsp;|&nbsp; {n} functions analysed &nbsp;|&nbsp; {corpus_label} corpus</p>
</header>

<div class="summary-cards">
  <div class="card"><div class="val">{n}</div><div class="lbl">Functions</div></div>
  <div class="card"><div class="val" style="color:#4ade80">{avg_energy}/10</div><div class="lbl">Avg Energy</div></div>
  <div class="card"><div class="val" style="color:#a78bfa">{avg_debt}/10</div><div class="lbl">Avg Debt</div></div>
  <div class="card"><div class="val" style="color:#f87171">{avg_safety}/10</div><div class="lbl">Avg Safety Risk</div></div>
  <div class="card"><div class="val">{grade_dist}</div><div class="lbl">Most common grade</div></div>
</div>

<div class="container">
  <div class="chart-wrap">
    <h2>Energy (X) · Debt (Y) · Safety (Z, bubble size) — hover for details</h2>
    <canvas id="chart" width="560" height="420"></canvas>
    <div class="legend" id="legend"></div>
  </div>
  <div class="table-wrap">
    <h2 style="color:#94a3b8; margin-bottom:1rem">Function Scores</h2>
    <table>
      <thead><tr>
        <th>Function</th><th>E</th><th>D</th><th>S</th><th>Grade</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>

<footer>LegacyLens CodeBalance · Energy · Debt · Safety Scoring · {timestamp}</footer>

<script>
const DATA = {data_json};

// ── colour by category ──────────────────────────────────────────────────────
const CAT_COLORS = {{}};
const PALETTE = ["#38bdf8","#a78bfa","#4ade80","#fb923c","#f472b6","#facc15","#34d399"];
let ci = 0;
DATA.forEach(d => {{
  if (!CAT_COLORS[d.category]) CAT_COLORS[d.category] = PALETTE[ci++ % PALETTE.length];
}});

// ── legend ──────────────────────────────────────────────────────────────────
const leg = document.getElementById("legend");
Object.entries(CAT_COLORS).forEach(([cat, col]) => {{
  leg.innerHTML += `<div class="legend-item"><div class="dot" style="background:${{col}}"></div>${{cat}}</div>`;
}});

// ── table ───────────────────────────────────────────────────────────────────
const tbody = document.getElementById("tbody");
DATA.forEach(d => {{
  const gc = `grade-${{d.grade}}`;
  tbody.innerHTML += `<tr>
    <td style="color:${{CAT_COLORS[d.category]}}">${{d.name}}</td>
    <td>${{d.energy}}<span class="bar energy-bar" style="width:${{d.energy * 10}}px"></span></td>
    <td>${{d.debt}}<span class="bar debt-bar" style="width:${{d.debt * 10}}px"></span></td>
    <td>${{d.safety}}<span class="bar safety-bar" style="width:${{d.safety * 10}}px"></span></td>
    <td class="grade ${{gc}}">${{d.grade}}</td>
  </tr>`;
}});

// ── 2.5D scatter on canvas (isometric projection) ───────────────────────────
const canvas = document.getElementById("chart");
const ctx = canvas.getContext("2d");
const W = canvas.width, H = canvas.height;

function project(x, y, z) {{
  // Isometric: x=Energy(0-10), y=Debt(0-10), z=Safety(0-10)
  const iso_x = (x - z) * Math.cos(0.5);
  const iso_y = (x + z) * Math.sin(0.5) - y * 0.9;
  const cx = W * 0.5 + iso_x * 22;
  const cy = H * 0.72 - iso_y * 20;
  return [cx, cy];
}}

function drawAxes() {{
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 1;
  const labels = [["Energy →", 10, 0, 0], ["Debt ↑", 0, 10, 0], ["Safety ↗", 0, 0, 10]];
  labels.forEach(([lbl, ex, ey, ez]) => {{
    const [ox, oy] = project(0, 0, 0);
    const [tx, ty] = project(ex, ey, ez);
    ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(tx, ty); ctx.stroke();
    ctx.fillStyle = "#64748b"; ctx.font = "11px system-ui";
    ctx.fillText(lbl, tx + 4, ty + 4);
  }});
  // Grid lines 0–10
  for (let i = 0; i <= 10; i += 2) {{
    ctx.strokeStyle = "#1e2d40"; ctx.lineWidth = 0.5;
    const [ax, ay] = project(i, 0, 0);
    const [bx, by] = project(i, 10, 0);
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
    const [cx2, cy2] = project(0, i, 0);
    const [dx, dy] = project(10, i, 0);
    ctx.beginPath(); ctx.moveTo(cx2, cy2); ctx.lineTo(dx, dy); ctx.stroke();
  }}
}}

function drawPoints() {{
  DATA.forEach(d => {{
    const [px, py] = project(d.energy, d.debt, d.safety);
    const r = 8 + d.safety * 2;   // safety = bubble size
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = CAT_COLORS[d.category] + "cc";
    ctx.fill();
    ctx.strokeStyle = CAT_COLORS[d.category];
    ctx.lineWidth = 1.5;
    ctx.stroke();
    // label
    ctx.fillStyle = "#e2e8f0";
    ctx.font = "10px system-ui";
    ctx.fillText(d.name, px + r + 3, py + 4);
  }});
}}

ctx.clearRect(0, 0, W, H);
drawAxes();
drawPoints();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Grade palette helpers
# ---------------------------------------------------------------------------

GRADE_ORDER = ["A", "B", "C", "D", "F"]


def grade_color(g: str) -> str:
    return {"A": "#4ade80", "B": "#86efac", "C": "#fde68a", "D": "#fb923c", "F": "#f87171"}.get(
        g, "#e2e8f0"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate 3D CodeBalance HTML report")
    parser.add_argument(
        "--output-dir", default="results", help="Output directory (default: results/)"
    )
    parser.add_argument(
        "--corpus",
        default="petclinic",
        choices=CORPORA.keys(),
        help="Corpus to analyze (default: petclinic)",
    )
    args = parser.parse_args()

    corpus_key = args.corpus
    corpus_data = CORPORA[corpus_key]
    funcs = corpus_data["functions"]
    corpus_label = corpus_data["label"]
    output_filename = corpus_data["output"]

    print(f"Scoring {len(funcs)} functions from {corpus_label} corpus...")

    rows = []
    for fn in funcs:
        score = score_code(fn["code"], function_name=fn["name"])
        rows.append(
            {
                "name": fn["name"],
                "category": fn["category"],
                "energy": score.energy,
                "debt": score.debt,
                "safety": score.safety,
                "total": score.total,
                "grade": score.grade,
            }
        )
        print(
            f"  {fn['name']:30s}  E={score.energy} D={score.debt} S={score.safety}  [{score.grade}]"
        )

    # Summary stats
    n = len(rows)
    avg_e = round(sum(r["energy"] for r in rows) / n, 1)
    avg_d = round(sum(r["debt"] for r in rows) / n, 1)
    avg_s = round(sum(r["safety"] for r in rows) / n, 1)
    from collections import Counter

    grade_dist = Counter(r["grade"] for r in rows).most_common(1)[0][0]

    # Render HTML
    html = HTML_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        n=n,
        avg_energy=avg_e,
        avg_debt=avg_d,
        avg_safety=avg_s,
        grade_dist=grade_dist,
        corpus_label=corpus_label,
        data_json=json.dumps(rows, indent=2),
    )

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / output_filename
    html_path.write_text(html)
    print(f"\nHTML report saved: {html_path}")
    print("Open it in any browser — no dependencies required.")


if __name__ == "__main__":
    main()
