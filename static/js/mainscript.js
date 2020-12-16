//Run page display tiles
$(document).ready(function(){
	$("#spp").change(function(){
		var selected = $(this).val();
		if (selected == "Human") {
			$(".form__genome").css("display", "grid");
			$('select[name="genome"]').hide();
			$("#HS_genome").show();
		} else if (selected == "Mouse") {
			$(".form__genome").css("display", "grid");
			$('select[name="genome"]').hide();
			$("#MM_genome").show();
		} else if (selected == "Rat") {
			$(".form__genome").css("display", "grid");
			$('select[name="genome"]').hide();
			$("#RN_genome").show();
		} else if (selected == "Droso") {
			$(".form__genome").css("display", "grid");
			$('select[name="genome"]').hide();
			S("#DM_genome").show();
		} else {
			$(".form__genome").css("display", "none");
		}
	});
});

$(document).ready(function(){
	$('select[name="genome"]').change(function(){
		var selected = $(this).val();
		if (selected != "default"){
			$(".form__build").css("display", "grid");
		} else {
			$(".form__build").css("display", "none");
		}
	});
});

$(document).ready(function(){
	$("#annotation").change(function(){
		var selected = $(this).val();
		if (selected != "default"){
			$(".form__vcf").css("display", "grid");
		} else {
			$(".form__vcf").css("display", "none");
		}
	});
});

//Submit abling
$(document).ready(function(){
	$(".form__submit").click(function(){
		$(".form__success").css("display", "grid");
	});
});

$(document).ready(function(){
	$('input[name="Upload VCF"]').click(function(){
		$(".form__submit").prop("disabled", false);
	});
});
