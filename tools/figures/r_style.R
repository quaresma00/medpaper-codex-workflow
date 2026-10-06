# Shared, deterministic R publication graphics. No model fitting or package installation.
medpaper_require <- function(packages) {
  missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing)) stop("Missing R packages: ", paste(missing, collapse = ", "),
                            ". Restore the study's renv environment; do not switch languages silently.")
}

medpaper_theme <- function(base_size = 9, family = "Arial") {
  medpaper_require("ggplot2")
  ggplot2::theme_classic(base_size = base_size, base_family = family) +
    ggplot2::theme(text = ggplot2::element_text(colour = "black"),
                   axis.line = ggplot2::element_line(linewidth = 0.25),
                   axis.ticks = ggplot2::element_line(linewidth = 0.25),
                   legend.position = "bottom", legend.title = ggplot2::element_blank(),
                   plot.margin = ggplot2::margin(4, 4, 4, 4, unit = "mm"),
                   plot.background = ggplot2::element_rect(fill = "white", colour = NA))
}

medpaper_palette <- c("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9")

medpaper_result <- function(relative_path) {
  medpaper_require("jsonlite")
  allowed <- jsonlite::fromJSON(Sys.getenv("MEDPAPER_SOURCE_RESULTS", "[]"))
  if (!relative_path %in% allowed) stop("Undeclared figure result input: ", relative_path)
  jsonlite::fromJSON(file.path(Sys.getenv("MEDPAPER_PROJECT"), relative_path), simplifyVector = FALSE)
}

medpaper_layers <- function(plot) {
  # Observe ggplot's built layers, not user-supplied booleans for mandatory elements.
  if (!inherits(plot, "ggplot")) return(NULL)
  built <- ggplot2::ggplot_build(plot)
  geom_names <- vapply(built$plot$layers, function(x) class(x$geom)[1], character(1))
  summary <- lapply(seq_along(geom_names), function(i) {
    d <- built$data[[i]]
    list(geom = geom_names[i], rows = nrow(d),
         xintercept = if ("xintercept" %in% names(d)) unique(d$xintercept) else numeric(),
         slope = if ("slope" %in% names(d)) unique(d$slope) else numeric(),
         intercept = if ("intercept" %in% names(d)) unique(d$intercept) else numeric(),
         ymin = if ("ymin" %in% names(d)) min(d$ymin, na.rm = TRUE) else NULL,
         xmin = if ("xmin" %in% names(d)) min(d$xmin, na.rm = TRUE) else NULL,
         shape = if ("shape" %in% names(d)) unique(d$shape) else numeric(),
         group_sizes = if ("group" %in% names(d)) as.integer(table(d$group)) else integer())
  })
  g <- ggplot2::ggplotGrob(plot)
  legends <- grepl("^guide-box", g$layout$name)
  has_legend <- any(vapply(g$grobs[legends], function(x) !inherits(x, "zeroGrob"), logical(1)))
  label <- function(name) {
    x <- built$plot$labels[[name]]
    if (is.null(x)) "" else paste(as.character(x), collapse = " ")
  }
  ranges <- lapply(built$layout$panel_params, function(x) list(x = x$x.range, y = x$y.range))
  list(layers = summary, x_label = label("x"), y_label = label("y"),
       legend = has_legend, ranges = ranges)
}

medpaper_save <- function(plot, stem, width = "single", height_mm = 75, dpi = 600,
                         panels = list(plot), tiff = FALSE) {
  medpaper_require(c("ggplot2", "jsonlite", "ragg", "svglite", "systemfonts"))
  output <- Sys.getenv("MEDPAPER_RENDER_STEM")
  if (!nzchar(output)) stop("Use tools/figures/render_r.py; a managed staging directory is required.")
  if (basename(stem) != basename(output)) stop("Figure script stem differs from the requested plan entry.")
  widths <- c(single = 90, `1.5` = 140, double = 180)
  if (!width %in% names(widths) || !is.finite(height_mm) || height_mm <= 0 || dpi < 300)
    stop("Invalid publication dimensions/resolution")
  if (!inherits(plot, c("ggplot", "grob", "gTree", "gtable")))
    stop("Plot must be a ggplot/patchwork or grid grob; use the dedicated R package's grid/ggplot export.")
  if (inherits(plot, "patchwork") && length(panels) == 1L)
    stop("For patchwork give panels=list(actual_component_ggplots) for structural inspection.")
  dir.create(dirname(output), recursive = TRUE, showWarnings = FALSE)
  # Grid measures font metrics on the active device. Opening the same system-font SVG
  # device first prevents a default PostScript device from rejecting installed Arial.
  svglite::svglite(paste0(output, ".svg"), width = unname(widths[width]) / 25.4,
                   height = height_mm / 25.4, bg = "white")
  svg_device <- grDevices::dev.cur()
  on.exit(if (grDevices::dev.cur() == svg_device) grDevices::dev.off(), add = TRUE)
  metadata <- list(schema_version = 1L, engine = "R", width_class = width,
                   size_mm = c(unname(widths[width]), height_mm), dpi = dpi,
                   panels = Filter(Negate(is.null), lapply(panels, medpaper_layers)),
                   r_version = R.version.string,
                   packages = setNames(lapply(c("ggplot2", "jsonlite", "ragg", "svglite", "systemfonts"),
                         function(p) as.character(utils::packageVersion(p))),
                         c("ggplot2", "jsonlite", "ragg", "svglite", "systemfonts")))
  if (inherits(plot, "ggplot")) print(plot) else {
    grid::grid.newpage()
    grid::grid.draw(plot)
  }
  grDevices::dev.off()
  # Explicit objects and physical sizes avoid last-plot/device-size surprises.
  ggplot2::ggsave(paste0(output, ".pdf"), plot = plot, device = grDevices::cairo_pdf,
                 width = unname(widths[width]), height = height_mm, units = "mm", bg = "white")
  ggplot2::ggsave(paste0(output, ".png"), plot = plot, device = ragg::agg_png,
                 width = unname(widths[width]), height = height_mm, units = "mm", dpi = dpi, bg = "white")
  if (tiff) ggplot2::ggsave(paste0(output, ".tiff"), plot = plot, device = ragg::agg_tiff,
                 width = unname(widths[width]), height = height_mm, units = "mm", dpi = dpi,
                 compression = "lzw", bg = "white")
  jsonlite::write_json(metadata, paste0(output, ".rmeta.json"), auto_unbox = TRUE,
                       pretty = TRUE, null = "null", na = "null")
  invisible(metadata)
}
