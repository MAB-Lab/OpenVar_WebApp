//Loading results page

$(document).ready(function() {
	$('.error__grid').css("display", "none");
	$('header__study_name').hide();
	$('.no_results__message').hide();
	$('#collapse__genes').hide();
	$('#collapse__hotspots').hide();
	$('#running_animation').hide();
	$('#deleted_file_img').hide();
	$('#not_launched_img').hide();

	var guid = location.pathname.substr(9);
	console.log(guid)
	
	fetch("/openvar/" + guid + "/json").then( function(response) {
		response.json().then( function(data) {
			if (data.outcome == 'success') {

				$('#header__study_name').text('Study: ' + data.study_name).show();

				$('.results__downloads').css('display', 'grid');
				$('#dwnld__all').attr("href", "/openvar/" + guid + "/download_all");
				$('#dwnld__annvcf').attr("href", "/openvar/" + guid + "/download_annvcf");
				$('#dwnld__tsv').attr("href", "/openvar/" + guid + "/download_tsv");

				$('.results__stats').css('display', 'grid');
				$(function() {
					$.each(data.general_stats, function(key, item) {
						$('<tr>').append(
						$('<td>').text(key),
						$('<td>').text(item.toLocaleString()).css('font-family', 'Courier').css('text-align', 'right')).appendTo('#results_stats');
					});
				});

				$('.results__chr').css('display', 'grid');
				$(function() {
					$.each(data.chromosomes, function(key, item){
						$('<tr>').append(
						$('<td>').text(key),
						$('<td>').text(item.toLocaleString()).css('font-family', 'Courier').css('text-align', 'right')).appendTo('#results_chr_tbody');
					});
				});

				var pie_chr = document.getElementById('chrom__pieChart');
				var chrom_pie = new Chart(pie_chr, {
					type: 'pie',
					data: {
						labels: Object.keys(data.chromosomes),
						datasets: [{
							label: 'Number of variants per chromosome',
							data: Object.values(data.chromosomes),
							backgroundColor: ['#000000','#000d1a','#001a33','#00264d','#003366','#004080','#004d99','#0059b3','#0066cc','#0073e6','#0080ff','#1a8cff','#3399ff','#4da6ff','#66b3ff','#80bfff','#99ccff','#b3d9ff','#b3ccff','#ccddff', '#cce6ff','#e6f2ff','#e6eeff','#e6e6ff','#ffffff'],
							borderColor: '#fdfddb'
						}]
					},
					options: { legend: { display: false, }, layout: { padding: { left: 0, right: 0, top: 0, bottom: 0 } }, title: { display: true, text: 'Number of variants per chromosome', fontSize: 16} },
				});

				if (data.gene_allnulls == 'False') {
					$('.results__gene').css('display', 'grid');
					$('#see_all__genes').attr('href', ("/openvar/" + guid + '/all_genes'));
					$(function(){
						$.each(data.top10_genes, function(key, item){
							$('<tr>').append(
							$('<td>').text(key),
							$('<td>').text((Math.round(item*100)/100).toLocaleString()).css('font-family', 'Courier')).appendTo('#results_gene_tbody');
						});
					});

					$('#see_100__genes').on('click', function() {
						$('#results_gene_tbody').empty();
						$.each(data.top100_genes, function(key, item){
							$('<tr>').append(
							$('<td>').text(key),
							$('<td>').text((Math.round(item*100)/100).toLocaleString()).css('font-family', 'Courier')).appendTo('#results_gene_tbody');
						});
						$('#see_100__genes').hide();
						$('#collapse__genes').show();
					});

					$('#collapse__genes').on('click', function(){
						$('#results_gene_tbody').empty();
						$.each(data.top10_genes, function(key, item){
							$('<tr>').append(
							$('<td>').text(key),
							$('<td>').text((Math.round(item*100)/100).toLocaleString()).css('font-family', 'Courier')).appendTo('#results_gene_tbody');
						});
						$('#see_100__genes').show();
						$('#collapse__genes').hide();
					});

					var bar_genes = document.getElementById('gene__barChart');
					var genes_bar = new Chart(bar_genes, {
						type: 'bar',
						data: {
							labels: Object.keys(data.top100_genes),
							datasets: [{
								label: 'Mutations / kb (top 100 genes)',
								data: Object.values(data.top100_genes),
								backgroundColor: '#bde2f8',
							}]
						},
						options: { legend: { display: false }, layout: { padding: { left: 0, right: 0, top: 0, bottom: 0 } }, scales:{ yAxes:[{scaleLabel:{display:true, labelString: 'Genomic variants per Kb'} }] }, title: { display: true, text: 'Mutations / kb per gene (top 100)', fontSize: 16} },
					});
				} else {
					$('.results__gene_allnulls').css('display', 'grid');
				}

				console.log(Object.keys(data.general_stats).length);
				if (Object.keys(data.general_stats).length == 6) {
					if (data.prot_allnulls == 'False') {
						$('.results__protein').css('display', 'grid');
						$(function() {
							$.each(data.prot_stats, function(key, item){
								$('<tr>').append(
								$('<td>').text(key),
								$('<td>').text(item.toLocaleString()).css('font-family', 'Courier').css('text-align', 'right')).appendTo('#results_prot_tbody');
							});
						});
						$(function() {
							$.each(data.prot_counts, function(key, item){
								$('<tr>').append(
								$('<td>').text(key),
								$('<td>').text((Math.round(item.Low*100)/100).toLocaleString()).css('font-family', 'Courier'),
								$('<td>').text((Math.round(item.Medium*100)/100).toLocaleString()).css('font-family', 'Courier'),
								$('<td>').text((Math.round(item.High*100)/100).toLocaleString()).css('font-family', 'Courier')).appendTo('#results_protFC_tbody');
							});
						});

						var bar_FC = document.getElementById('prot__FCbarChart');
						var FC_bar = new Chart(bar_FC, {
							type:'horizontalBar',
							data:{
								labels: Object.keys(data.prot_counts['Fold Change']),
								datasets:[{
									label: 'Fold-change (gain from deeper annotation)',
									data: Object.values(data.prot_counts['Fold Change']),
									backgroundColor: ['#e6f2ff', '#66b3ff', '#004d99']
								}]
							},
							options:{ legend:{ display: false }, layout:{ padding: { left: 0, right: 0, top: 0, bottom: 0 } }, scales:{ xAxes:[{scaleLabel:{display:true, labelString: 'Fold-change'}}] }, title: { display: true, text: 'Fold-change gained from deeper annotation per impact', fontSize: 16} },
						});

						var stackedbar_imp = document.getElementById('prot__ImpactbarChart');
						var imp_stackedbar = new Chart(stackedbar_imp, {
							type: 'horizontalBar',
							data: {
								labels: Object.keys(data.graph_counts['Alternative protein']),
								datasets:[{
									label: 'In known proteins',
									data: Object.values(data.graph_counts['Reference protein']),
									backgroundColor: '#39ac73'
								}, {
									label: 'In alternative proteins',
									data: Object.values(data.graph_counts['Alternative protein']),
									backgroundColor: '#9fdfbf'
								}]
							},
							options: {legend: {display: true, position: 'bottom'}, layout:{ padding: {left: 0, right:0, top: 0, bottom: 0} }, scales:{ xAxes:[{scaleLabel:{display:true, labelString: 'Count of genomic variants'}, stacked: true}], yAxes: [{stacked: true}] }, title: { display: true, text: 'Number of variants per impact', fontSize: 16} },
						});
					} else {
						$('.results__protein_allnulls').css('display', 'grid');
					}

					if (data.hotspots_allnulls == 'False') {
						$('.results__altHotSpot').css('display', 'grid');
						$('#see_all__hotspots').attr('href', ("/openvar/" + guid + '/hotspots_all_genes'));
						$(function() {
							$.each(data.hotspots_top10, function(key, item){
								$('<tr>').append(
								$('<td>').text(key),
								$('<td>').text((Math.round(item[0]*100)/100).toLocaleString()).css('font-family', 'Courier'),
								$('<td>').text(item[1].toLocaleString()).css('font-family', 'Courier')).appendTo('#results_hotspots_tbody');
							});
						});

						$('#see_100__hotspots').on('click', function() {
                                        		$('#results_hotspots_tbody').empty();
                                        		$.each(data.hotspots_top100, function(key, item){
								$('<tr>').append(
								$('<td>').text(key),
								$('<td>').text(Math.round(item[0]*100)/100),
								$('<td>').text(item[1].toLocaleString()).css('font-family', 'Courier')).appendTo('#results_hotspots_tbody');
							});
							$('#see_100__hotspots').hide();
							$('#collapse__hotspots').show();
						});

						$('#collapse__hotspots').on('click', function(){
							$('#results_hotspots_tbody').empty();
							$.each(data.hotspots_top10, function(key, item){
								$('<tr>').append(
								$('<td>').text(key),
								$('<td>').text(Math.round(item[0]*100)/100),
								$('<td>').text(item[1].toLocaleString()).css('font-family', 'Courier')).appendTo('#results_hotspots_tbody');
							});
							$('#see_100__hotspots').show();
							$('#collapse__hotspots').hide();
						});

						var hotspot_bar = document.getElementById('hotspot__barChart');
						var bar_hotspot = new Chart(hotspot_bar, {
							type: 'bar',
							data: {
								labels: Object.keys(data.hotspot_graph.one_snp),
								datasets: [{
									label: 'Count of altORFs with one SNP',
									data: Object.values(data.hotspot_graph.one_snp),
									backgroundColor: '#f3a6fc',
									average_impact: Object.values(data.mean_impact_per_bin.one_snp),
								}, {
									label: 'Count of altORFs with 2 to 10 SNPs',
									data: Object.values(data.hotspot_graph.one_ten),
									backgroundColor: '#cf5fe3',
									average_impact: Object.values(data.mean_impact_per_bin.one_ten),
								}, {
									label: 'Count of altORFs with at least 10 SNPs',
									data: Object.values(data.hotspot_graph.over_ten),
									backgroundColor: '#7b198c',
									average_impact: Object.values(data.mean_impact_per_bin.over_ten),
								}]
							},
							options: { legend: {display: true}, layout: { padding: {left:0, right:0, top:0, bottom:0} }, scales:{ xAxes:[{scaleLabel: {display: true, labelString: "Portion of gene's variants in altORF"}, stacked: true}], yAxes: [{scaleLabel: {display: true, labelString: 'Count of altORFs'}, stacked: true}]}, title: { display: true, text:'Mutational hotspots on alternative proteins', fontSize:16}, tooltips: { callbacks: { afterLabel: function(t, d){ return 'Average impact of SNPs: ' + Math.round(d.datasets[t.datasetIndex].average_impact[t.index]*100)/100 } }} },
						});
					} else {
						$('.results__altHotSpot_allnulls').css('display', 'grid');
					}
				} else {
					$('.results__altHotSpot').css('display', 'none');
					$('.results__protein').css('display', 'none');
				}

			} else {
				$('.error__grid').css("display", "grid");
				$('.no_results__message').text(data.message).show();
				if (data.tag == 'running') {
					$('#running_animation').show();
				} else if (data.tag == 'deleted') {
					$('#deleted_file_img').show();	
				} else {
					$('#not_launched_img').show();
				}
			}
		});
	
	});
});

