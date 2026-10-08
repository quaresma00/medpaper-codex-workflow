# Observed provenance; source this helper from the actual R analysis producer.
medpaper_write_results <- function(name, payload, seed, inputs) {
  if (!requireNamespace("jsonlite", quietly=TRUE)) stop("Restore jsonlite in the study environment")
  project <- normalizePath(Sys.getenv("MEDPAPER_PROJECT"), winslash="/", mustWork=TRUE)
  filearg <- grep("^--file=", commandArgs(FALSE), value=TRUE)
  if (length(filearg) != 1L) stop("Run the actual producer with Rscript --file, not an inline receipt repair")
  script <- normalizePath(sub("^--file=", "", filearg), winslash="/", mustWork=TRUE)
  prefix <- paste0(project, "/")
  if (!startsWith(tolower(script), tolower(paste0(prefix, "03_analysis/code/")))) stop("Invalid producer location")
  if (length(commandArgs(TRUE))) stop("Declare configuration as input files, not undeclared CLI arguments")
  if (length(seed)!=1L || !is.numeric(seed) || !is.finite(seed) || seed<0 || seed!=floor(seed)) stop("Invalid seed")
  if (basename(name)!=name || !grepl("^[^/\\\\]+\\.json$", name)) stop("Invalid result filename")
  if (!is.list(payload) || is.null(names(payload)) || "environment" %in% names(payload)) stop("Invalid result object")
  validate <- function(x) {
    if (is.numeric(x) && any(!is.finite(x))) stop("Convert missing values explicitly to NULL; no NaN/Infinity")
    if (is.list(x)) lapply(x, validate)
    invisible(NULL)
  }
  validate(payload)
  if (!length(inputs) || anyDuplicated(inputs)) stop("Declare every actual input once")
  safe <- function(rel) {
    if (grepl("^(/|[A-Za-z]:)|(^|[/\\\\])\\.\\.([/\\\\]|$)",rel)) stop("Unsafe relative input")
    p <- normalizePath(file.path(project, rel), winslash="/", mustWork=TRUE)
    if (!startsWith(tolower(p),tolower(prefix)) || dir.exists(p) || identical(p,script)) stop("Invalid input")
    p
  }
  # Use the same streaming SHA-256 implementation as the Python writer; no extra R hash package.
  python <- Sys.getenv("MEDPAPER_PYTHON")
  if (!nzchar(python)) stop("Run R through tools/analysis/reproduce.py run so MEDPAPER_PYTHON is bound")
  hash <- function(p) {
    code <- "import hashlib,sys; f=open(sys.argv[1],'rb'); print(hashlib.file_digest(f,'sha256').hexdigest())"
    answer <- system2(python, c("-c", shQuote(code), shQuote(p)), stdout=TRUE)
    if (length(answer)!=1L || !grepl("^[0-9a-f]{64}$",answer)) stop("SHA-256 failed")
    toupper(answer)
  }
  ih <- setNames(lapply(inputs,function(r) hash(safe(r))), gsub("\\\\","/",inputs))
  packages <- setNames(lapply(loadedNamespaces(),function(n) as.character(utils::packageVersion(n))),loadedNamespaces())
  payload$environment <- list(schema_version=1L, language="R", version=as.character(getRversion()),
    packages=packages, seed=seed, script=substring(script,nchar(prefix)+1), script_sha256=hash(script),
    inputs=ih, written_at=format(Sys.time(),"%Y-%m-%dT%H:%M:%OS6Z",tz="UTC"),writer="medpaper-results-v1")
  out <- file.path(project,"03_analysis/results",name)
  if (file.exists(file.path(project,".wf/state.json"))) {
    code <- "import pathlib,sys; from wfcore.revision import guard_outputs; guard_outputs(pathlib.Path(sys.argv[1]),[pathlib.Path(sys.argv[2])])"
    if (system2(python,c("-c",shQuote(code),shQuote(project),shQuote(out)))!=0) stop("Result is outside approved revision scope")
  }
  dir.create(dirname(out),recursive=TRUE,showWarnings=FALSE)
  temporary <- tempfile(pattern=basename(out),tmpdir=dirname(out))
  on.exit(unlink(temporary),add=TRUE)
  writeLines(jsonlite::toJSON(payload,auto_unbox=TRUE,null="null",digits=I(17),pretty=TRUE),temporary,useBytes=TRUE)
  if (.Platform$OS.type=="windows") {
    # pathlib.replace uses Windows replacement semantics without deleting the old output first.
    code <- "import pathlib,sys; pathlib.Path(sys.argv[1]).replace(sys.argv[2])"
    status <- system2(python,c("-c",shQuote(code),shQuote(temporary),shQuote(out)))
    if(status!=0) stop("Atomic result replacement failed")
  } else if (!file.rename(temporary,out)) stop("Atomic result replacement failed")
  if (file.exists(file.path(project,".wf/state.json"))) {
    code <- "import pathlib,sys; from wfcore.revision import record_build; p=pathlib.Path(sys.argv[1]); record_build(p,pathlib.Path(sys.argv[2]),[p/r for r in sys.argv[3:]])"
    if(system2(python,c("-c",shQuote(code),shQuote(project),shQuote(out),shQuote(substring(script,nchar(prefix)+1)),shQuote(inputs)))!=0) stop("Result build receipt failed")
  }
  invisible(out)
}
