parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  values <- list(
    limit = 24,
    min_samples = 3,
    max_samples = 100,
    manifest = "data/manifests/bulk_manifest.csv",
    raw_dir = "data/raw/bulk",
    download = FALSE
  )
  i <- 1
  while (i <= length(args)) {
    key <- args[[i]]
    if (key == "--download") {
      values$download <- TRUE
      i <- i + 1
      next
    }
    if (i == length(args)) stop(paste("Missing value for", key))
    value <- args[[i + 1]]
    if (key == "--limit") values$limit <- as.integer(value)
    else if (key == "--min-samples") values$min_samples <- as.integer(value)
    else if (key == "--max-samples") values$max_samples <- as.integer(value)
    else if (key == "--manifest") values$manifest <- value
    else if (key == "--raw-dir") values$raw_dir <- value
    else stop(paste("Unknown argument", key))
    i <- i + 2
  }
  values
}

require_package <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop(paste("Missing package", pkg, "- install it before running this script."))
  }
}

text_match <- function(df, pattern) {
  haystack <- apply(df, 1, function(row) paste(row, collapse = " "))
  grepl(pattern, haystack, ignore.case = TRUE)
}

write_manifest <- function(projects, manifest_path, raw_dir, limit, min_samples, max_samples) {
  projects <- projects[projects$n_samples >= min_samples & projects$n_samples <= max_samples, , drop = FALSE]
  preferred <- projects[text_match(projects, "pbmc|peripheral blood|blood|mononuclear"), , drop = FALSE]
  fallback <- projects[!projects$project %in% preferred$project, , drop = FALSE]
  preferred$fallback_reason <- ""
  fallback$fallback_reason <- "not enough PBMC/blood projects"
  selected <- rbind(preferred, fallback)
  selected <- selected[seq_len(min(nrow(selected), limit)), , drop = FALSE]

  rows <- data.frame(
    project = selected$project,
    project_home = selected$project_home,
    project_type = selected$project_type,
    n_samples = selected$n_samples,
    local_dir = file.path(raw_dir, selected$project),
    selected = TRUE,
    downloaded = file.exists(file.path(raw_dir, selected$project, "gene_counts.tsv.gz")),
    preprocessed = FALSE,
    ingested = FALSE,
    fallback_reason = selected$fallback_reason,
    error = "",
    stringsAsFactors = FALSE
  )

  dir.create(dirname(manifest_path), recursive = TRUE, showWarnings = FALSE)
  dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
  write.csv(rows, manifest_path, row.names = FALSE)
  rows
}

download_manifest <- function(manifest_path, projects) {
  require_package("recount3")
  require_package("SummarizedExperiment")
  manifest <- read.csv(manifest_path, stringsAsFactors = FALSE)
  for (i in seq_len(nrow(manifest))) {
    if (!isTRUE(manifest$selected[[i]])) next
    project_dir <- manifest$local_dir[[i]]
    counts_path <- file.path(project_dir, "gene_counts.tsv.gz")
    meta_path <- file.path(project_dir, "sample_metadata.tsv.gz")
    if (file.exists(counts_path) && file.exists(meta_path)) {
      manifest$downloaded[[i]] <- TRUE
      next
    }
    dir.create(project_dir, recursive = TRUE, showWarnings = FALSE)
    tryCatch({
      project_info <- projects[
        projects$project == manifest$project[[i]] &
          projects$project_home == manifest$project_home[[i]] &
          projects$project_type == manifest$project_type[[i]],
        ,
        drop = FALSE
      ]
      if (nrow(project_info) == 0) stop(paste("Project no longer available:", manifest$project[[i]]))
      project_info <- project_info[1, , drop = FALSE]
      rse <- recount3::create_rse(project_info, type = "gene")
      counts <- SummarizedExperiment::assay(rse)
      metadata <- as.data.frame(SummarizedExperiment::colData(rse))
      write.table(counts, gzfile(counts_path), sep = "\t", quote = FALSE, col.names = NA)
      write.table(metadata, gzfile(meta_path), sep = "\t", quote = FALSE, col.names = NA)
      manifest$downloaded[[i]] <- TRUE
      manifest$error[[i]] <- ""
    }, error = function(e) {
      manifest$downloaded[[i]] <- FALSE
      manifest$error[[i]] <- conditionMessage(e)
    })
    write.csv(manifest, manifest_path, row.names = FALSE)
  }
}

args <- parse_args()
require_package("recount3")
projects <- recount3::available_projects("human")

if (args$download && file.exists(args$manifest)) {
  download_manifest(args$manifest, projects)
} else {
  manifest <- write_manifest(
    projects,
    args$manifest,
    args$raw_dir,
    args$limit,
    args$min_samples,
    args$max_samples
  )
  message("Wrote ", nrow(manifest), " candidates to ", args$manifest)
  if (args$download) download_manifest(args$manifest, projects)
}
