# Small graph recipes consuming approved, full-precision results. Never fit a model here.
medpaper_check_numeric <- function(data, columns) {
  if (!is.data.frame(data) || !nrow(data) || !all(columns %in% names(data))) stop("Missing complete plotting data")
  for (column in columns) if (!is.numeric(data[[column]]) || any(!is.finite(data[[column]])))
    stop("Non-numeric/missing plotting input: ",column,"; resolve at the analysis owner, never silently drop rows")
}

medpaper_forest <- function(data, measure="Adjusted odds ratio", null=1, log_scale=TRUE) {
  medpaper_require("ggplot2")
  medpaper_check_numeric(data,c("estimate","lower","upper"))
  if (!"label" %in% names(data) || anyDuplicated(data$label) || any(!nzchar(data$label))) stop("Unique clinical row labels required")
  if (any(data$lower>data$estimate | data$estimate>data$upper)) stop("Invalid confidence interval")
  if (log_scale && (any(data$lower<=0) || null<=0)) stop("Logarithmic effect measures must be positive")
  data$label <- factor(data$label,levels=rev(data$label))
  p <- ggplot2::ggplot(data,ggplot2::aes(x=estimate,y=label)) +
    ggplot2::geom_vline(xintercept=null,linetype="dashed",linewidth=.3) +
    ggplot2::geom_errorbar(ggplot2::aes(xmin=lower,xmax=upper),orientation="y",width=.15,linewidth=.35) +
    ggplot2::geom_point(size=2) + ggplot2::labs(x=paste0(measure," (95% CI)"),y="Clinical group") + medpaper_theme()
  if(log_scale) p <- p + ggplot2::scale_x_log10()
  # Exact effect/CI values can be printed by a study-specific aligned statistics column.
  # This intentionally does not guess the right-hand layout or clinical wording.
  p
}

medpaper_roc <- function(data, legend_title=NULL) {
  medpaper_require("ggplot2")
  medpaper_check_numeric(data,c("fpr","tpr"))
  if (!"group" %in% names(data) || any(data$fpr<0 | data$fpr>1 | data$tpr<0 | data$tpr>1)) stop("Invalid approved ROC coordinates/groups")
  ggplot2::ggplot(data,ggplot2::aes(x=fpr,y=tpr,colour=group,group=group)) +
    ggplot2::geom_abline(slope=1,intercept=0,linetype="dashed",linewidth=.3,colour="grey50") +
    ggplot2::geom_path(linewidth=.5) + ggplot2::coord_equal(xlim=c(0,1),ylim=c(0,1)) +
    ggplot2::labs(x="1 - Specificity",y="Sensitivity",colour=legend_title) + medpaper_theme()
}

medpaper_calibration <- function(data, probability_label="Outcome probability") {
  medpaper_require("ggplot2")
  medpaper_check_numeric(data,c("predicted","observed"))
  if (!"group" %in% names(data) || any(data$predicted<0 | data$predicted>1 | data$observed<0 | data$observed>1)) stop("Invalid approved calibration coordinates/groups")
  ggplot2::ggplot(data,ggplot2::aes(x=predicted,y=observed,colour=group,group=group)) +
    ggplot2::geom_abline(slope=1,intercept=0,linetype="dashed",linewidth=.3,colour="grey50") +
    ggplot2::geom_line(linewidth=.5) + ggplot2::geom_point(size=1.5) +
    ggplot2::coord_equal(xlim=c(0,1),ylim=c(0,1)) +
    ggplot2::labs(x=paste("Predicted",tolower(probability_label)),y=paste("Observed",tolower(probability_label))) + medpaper_theme()
}
