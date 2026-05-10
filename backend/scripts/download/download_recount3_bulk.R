parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  values <- list(
    manifest = "data/manifests/recount3_pbmc_bulk_manifest.csv",
    raw_dir = "data/raw/bulk/recount3_pbmc",
    project_list = "",
    write_template = FALSE,
    download = FALSE,
    organism = "human"
  )
  i <- 1
  while (i <= length(args)) {
    key <- args[[i]]
    if (key == "--write-template") {
      values$write_template <- TRUE
      i <- i + 1
      next
    }
    if (key == "--download") {
      values$download <- TRUE
      i <- i + 1
      next
    }
    if (i == length(args)) stop(paste("Missing value for", key))
    value <- args[[i + 1]]
    if (key == "--manifest") values$manifest <- value
    else if (key == "--raw-dir") values$raw_dir <- value
    else if (key == "--project-list") values$project_list <- value
    else if (key == "--organism") values$organism <- value
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

validate_columns <- function(df, required) {
  missing <- setdiff(required, colnames(df))
  if (length(missing) > 0) {
    stop(
      paste(
        "Missing required columns:",
        paste(missing, collapse = ", ")
      )
    )
  }
}

load_manifest <- function(manifest_path, raw_dir) {
  if (!file.exists(manifest_path)) {
    stop(
      paste(
        "Manifest not found at", manifest_path,
        "- create one with --write-template or provide --project-list."
      )
    )
  }
  manifest <- read.csv(manifest_path, stringsAsFactors = FALSE)
  validate_columns(manifest, c("project", "project_home", "project_type"))
  if (!"selected" %in% colnames(manifest)) manifest$selected <- TRUE
  if (!"downloaded" %in% colnames(manifest)) manifest$downloaded <- FALSE
  if (!"preprocessed" %in% colnames(manifest)) manifest$preprocessed <- FALSE
  if (!"ingested" %in% colnames(manifest)) manifest$ingested <- FALSE
  if (!"error" %in% colnames(manifest)) manifest$error <- ""
  if (!"local_dir" %in% colnames(manifest)) {
    manifest$local_dir <- file.path(raw_dir, manifest$project)
  }
  manifest
}

write_manifest_template <- function(manifest_path, raw_dir, project_list_path = "") {
  dir.create(dirname(manifest_path), recursive = TRUE, showWarnings = FALSE)
  dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
  if (nzchar(project_list_path)) {
    project_list <- read.csv(project_list_path, stringsAsFactors = FALSE)
    validate_columns(project_list, c("project"))
    if (!"project_home" %in% colnames(project_list)) {
      project_list$project_home <- "data_sources/sra"
    }
    if (!"project_type" %in% colnames(project_list)) {
      project_list$project_type <- "data_sources"
    }
    if (!"notes" %in% colnames(project_list)) {
      project_list$notes <- ""
    }
    rows <- data.frame(
      project = project_list$project,
      project_home = project_list$project_home,
      project_type = project_list$project_type,
      local_dir = file.path(raw_dir, project_list$project),
      selected = TRUE,
      downloaded = FALSE,
      preprocessed = FALSE,
      ingested = FALSE,
      notes = project_list$notes,
      error = "",
      stringsAsFactors = FALSE
    )
  } else {
    rows <- data.frame(
      project = c("SRPXXXXXX", "SRPYYYYYY"),
      project_home = c("data_sources/sra", "data_sources/sra"),
      project_type = c("data_sources", "data_sources"),
      local_dir = file.path(raw_dir, c("SRPXXXXXX", "SRPYYYYYY")),
      selected = c(TRUE, TRUE),
      downloaded = c(FALSE, FALSE),
      preprocessed = c(FALSE, FALSE),
      ingested = c(FALSE, FALSE),
      notes = c("replace with a human bulk PBMC recount3 project", "replace with a human bulk PBMC recount3 project"),
      error = c("", ""),
      stringsAsFactors = FALSE
    )
  }
  write.csv(rows, manifest_path, row.names = FALSE)
  message("Wrote manifest template to ", manifest_path)
  invisible(rows)
}

download_manifest <- function(manifest_path, raw_dir, organism) {
  require_package("recount3")
  require_package("SummarizedExperiment")
  manifest <- load_manifest(manifest_path, raw_dir)
  projects <- recount3::available_projects(organism)
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
      if (nrow(project_info) == 0) {
        stop(
          paste(
            "Project not found in recount3 available_projects():",
            manifest$project[[i]],
            "with",
            manifest$project_home[[i]],
            manifest$project_type[[i]]
          )
        )
      }
      project_info <- project_info[1, , drop = FALSE]
      rse <- recount3::create_rse(project_info, type = "gene")
      counts <- SummarizedExperiment::assay(rse)
      metadata <- as.data.frame(SummarizedExperiment::colData(rse))
      write.table(counts, gzfile(counts_path), sep = "\t", quote = FALSE, col.names = NA)
      write.table(metadata, gzfile(meta_path), sep = "\t", quote = FALSE, col.names = NA)
      manifest$downloaded[[i]] <- TRUE
      manifest$error[[i]] <- ""
      message("Downloaded ", manifest$project[[i]], " -> ", project_dir)
    }, error = function(e) {
      manifest$downloaded[[i]] <- FALSE
      manifest$error[[i]] <- conditionMessage(e)
      message("Failed ", manifest$project[[i]], ": ", conditionMessage(e))
    })
    write.csv(manifest, manifest_path, row.names = FALSE)
  }
}

args <- parse_args()

if (args$write_template) {
  write_manifest_template(args$manifest, args$raw_dir, args$project_list)
}

if (args$download) {
  download_manifest(args$manifest, args$raw_dir, args$organism)
}

if (!args$write_template && !args$download) {
  message(
    paste(
      "Nothing to do.",
      "Use --write-template to create a PBMC manifest template,",
      "or --download to fetch projects listed in the manifest."
    )
  )
}
