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

# Neutral selection diagram for cohorts/records, not an assertion of trial registration
# or checklist compliance. Counts are supplied individually from executed result exports.
# x/y are layout coordinates only; edges describe actual flow, not subtraction rules.
medpaper_selection_flow <- function(nodes, edges, box_width=.36, box_height=.16, family="Arial") {
  medpaper_require("ggplot2")
  medpaper_check_numeric(nodes,c("n","x","y"))
  if(!all(c("id","label") %in% names(nodes)) || anyNA(nodes$id) || anyNA(nodes$label) ||
     any(!nzchar(nodes$id)) || any(!nzchar(nodes$label)) || anyDuplicated(nodes$id) ||
     any(nodes$n<0 | nodes$n!=floor(nodes$n))) stop("Distinct nodes, clinical labels and nonnegative whole counts required")
  if(!is.data.frame(edges) || !nrow(edges) || !all(c("from","to") %in% names(edges)) ||
     anyNA(edges$from) || anyNA(edges$to) || any(!edges$from %in% nodes$id) ||
     any(!edges$to %in% nodes$id) || any(edges$from==edges$to) || anyDuplicated(edges)) stop("Declare actual connected source/destination nodes")
  if(length(box_width)!=1L || length(box_height)!=1L || !is.finite(box_width) || !is.finite(box_height) ||
     box_width<=0 || box_height<=0) stop("Positive box dimensions required")
  # Fail on cycles/unconnected nodes; do not turn a broken selection path into a tidy drawing.
  unseen <- nodes$id; roots <- setdiff(nodes$id,edges$to)
  if(length(roots)!=1L || any(!nodes$id %in% c(edges$from,edges$to))) stop("Use one source root and connect every actual node")
  pending <- roots
  while(length(pending)) {
    unseen <- setdiff(unseen,pending)
    pending <- unseen[!vapply(unseen,function(id) any(edges$from[edges$to==id] %in% unseen),logical(1))]
  }
  if(length(unseen)) stop("Selection edges contain a cycle")
  if(nrow(nodes)>1L) for(i in seq_len(nrow(nodes)-1L)) for(j in (i+1L):nrow(nodes))
    if(abs(nodes$x[i]-nodes$x[j])<box_width && abs(nodes$y[i]-nodes$y[j])<box_height)
      stop("Flow boxes overlap; change layout coordinates, not counts")
  wrapped <- lapply(nodes$label, function(x) strwrap(x,width=29))
  if(any(lengths(wrapped)>3L)) stop("Long flow labels need a larger measured layout or concise clinical wording")
  nodes$text <- paste0(vapply(wrapped,paste,character(1),collapse="\n"),"\nn = ",format(nodes$n,scientific=FALSE,trim=TRUE))
  a <- nodes[match(edges$from,nodes$id),]; b <- nodes[match(edges$to,nodes$id),]
  horizontal <- abs(b$x-a$x)>abs(b$y-a$y)
  sx <- a$x+ifelse(horizontal,sign(b$x-a$x)*box_width/2,0)
  sy <- a$y+ifelse(horizontal,0,sign(b$y-a$y)*box_height/2)
  ex <- b$x-ifelse(horizontal,sign(b$x-a$x)*box_width/2,0)
  ey <- b$y-ifelse(horizontal,0,sign(b$y-a$y)*box_height/2)
  links <- data.frame(x=sx,y=sy,xend=ex,yend=ey)
  ggplot2::ggplot() +
    ggplot2::geom_segment(data=links,ggplot2::aes(x=x,y=y,xend=xend,yend=yend),linewidth=.35,
                          arrow=grid::arrow(length=grid::unit(2,"mm"),type="closed")) +
    ggplot2::geom_rect(data=nodes,ggplot2::aes(xmin=x-box_width/2,xmax=x+box_width/2,
                                            ymin=y-box_height/2,ymax=y+box_height/2),fill="white",colour="black",linewidth=.35) +
    ggplot2::geom_text(data=nodes,ggplot2::aes(x=x,y=y,label=text),size=9/ggplot2::.pt,family=family,lineheight=.95) +
    ggplot2::coord_cartesian(xlim=range(nodes$x)+c(-1,1)*box_width*.65,
                         ylim=range(nodes$y)+c(-1,1)*box_height*.7,expand=FALSE) +
    ggplot2::theme_void(base_family=family) +
    ggplot2::theme(plot.margin=ggplot2::margin(3,3,3,3,unit="mm"),
                   plot.background=ggplot2::element_rect(fill="white",colour=NA))
}

medpaper_plot_groups <- function(data, fields) {
  if(!all(fields %in% names(data)) || anyNA(data[fields]) ||
     any(!vapply(data[fields],function(x) all(nzchar(as.character(x))),logical(1)))) stop("Complete clinical labels/groups required")
}

# A dose-response curve (including an already-fitted restricted cubic spline), not
# a spline estimator: exported reference, coordinates and uncertainty stay unchanged.
medpaper_dose_response <- function(data, x_label, y_label, null=NULL) {
  medpaper_check_numeric(data,c("exposure","estimate","lower","upper"))
  medpaper_plot_groups(data,"group")
  if(any(data$lower>data$estimate | data$estimate>data$upper) || anyDuplicated(data[c("group","exposure")])) stop("Complete unique dose/interval coordinates required")
  p <- ggplot2::ggplot(data,ggplot2::aes(x=exposure,y=estimate,colour=group,fill=group,group=group)) +
    ggplot2::geom_ribbon(ggplot2::aes(ymin=lower,ymax=upper),alpha=.15,colour=NA) +
    ggplot2::geom_line(linewidth=.5) + ggplot2::labs(x=x_label,y=y_label) + medpaper_theme()
  if(!is.null(null)) {
    if(length(null)!=1L || !is.finite(null)) stop("Explicit finite reference value required")
    p <- p+ggplot2::geom_hline(yintercept=null,linetype="dashed",linewidth=.3)
  }
  p
}

medpaper_decision_curve <- function(data, y_label="Net benefit") {
  medpaper_check_numeric(data,c("threshold","net_benefit"));medpaper_plot_groups(data,"group")
  if(any(data$threshold<=0 | data$threshold>=1) || anyDuplicated(data[c("group","threshold")])) stop("Unique source thresholds strictly between zero and one required")
  ggplot2::ggplot(data,ggplot2::aes(x=threshold,y=net_benefit,colour=group,group=group)) +
    ggplot2::geom_line(linewidth=.5) + ggplot2::labs(x="Threshold probability",y=y_label) + medpaper_theme()
}

medpaper_balance <- function(data, threshold=NULL, absolute=TRUE) {
  medpaper_check_numeric(data,"smd");medpaper_plot_groups(data,c("variable","group"))
  if(length(absolute)!=1L || !is.logical(absolute) || is.na(absolute) || anyDuplicated(data[c("group","variable")])) stop("Unique source variable/sample statistics and logical scale required")
  if(absolute) data$smd <- abs(data$smd)
  data$variable <- factor(data$variable,levels=rev(unique(data$variable)))
  p <- ggplot2::ggplot(data,ggplot2::aes(x=smd,y=variable,colour=group,shape=group)) +
    ggplot2::geom_point(size=2) + ggplot2::labs(x=if(absolute) "Absolute standardized mean difference" else "Standardized mean difference",y=NULL) + medpaper_theme()
  if(!is.null(threshold)) {
    if(length(threshold)!=1L || !is.finite(threshold) || threshold<=0) stop("Use the study's explicit positive balance threshold")
    p <- p+ggplot2::geom_vline(xintercept=if(absolute) threshold else c(-threshold,threshold),linetype="dashed",linewidth=.3)
  }
  p
}
