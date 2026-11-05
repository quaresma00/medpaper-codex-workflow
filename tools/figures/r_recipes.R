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

# One measured ggplot: exact source estimates beside their intervals, not a new
# model or multiple pseudo-panels. Explicit measure/null/scale prevent guessing
# an OR/HR/RR/linear coefficient from a generic result field called estimate.
medpaper_forest_table <- function(data, measure, null, log_scale, digits=2L,
                                  interval_label="95% CI", effect_header=NULL) {
  if (missing(measure) || missing(null) || missing(log_scale) ||
      length(measure)!=1L || is.na(measure) || !nzchar(measure) ||
      length(null)!=1L || !is.finite(null) || !is.logical(log_scale) || length(log_scale)!=1L || is.na(log_scale))
    stop("Explicit source-supported measure, null value and logical scale are required")
  if(length(digits)!=1L || !is.numeric(digits) || !is.finite(digits) || digits<0L || digits>8L || digits!=as.integer(digits))
    stop("Use explicit display precision from 0 to 8 digits")
  if(length(interval_label)!=1L || is.na(interval_label) || !nzchar(interval_label)) stop("Declare the actual interval label")
  p <- medpaper_forest(data,measure=measure,null=null,log_scale=log_scale)
  format_effect <- function(x) ifelse(x!=0 & round(x,digits)==0,
                                      formatC(x,format="g",digits=2),formatC(x,format="f",digits=digits))
  data$label <- factor(data$label,levels=rev(data$label))
  data$effect_text <- paste0(format_effect(data$estimate)," (",format_effect(data$lower)," to ",format_effect(data$upper),")")
  if(is.null(effect_header)) effect_header <- paste0(measure,"\n(",interval_label,")")
  p + ggplot2::geom_text(data=data,ggplot2::aes(x=Inf,y=label,label=effect_text),
                         inherit.aes=FALSE,hjust=-.08,size=9/ggplot2::.pt) +
    ggplot2::annotate("text",x=Inf,y=Inf,label=effect_header,hjust=-.08,vjust=-.15,
                       size=9/ggplot2::.pt,fontface="bold") +
    ggplot2::coord_cartesian(clip="off") + ggplot2::labs(x=measure,y=NULL) +
    ggplot2::theme(plot.margin=ggplot2::margin(12,48,4,4,unit="mm"))
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
