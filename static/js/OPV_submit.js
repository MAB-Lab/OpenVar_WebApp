// Scripts submit route
// Update values for genome versions based on species
$(document).ready(function() {
	let species_select = document.getElementById('user_input-species')
	let genome_select = document.getElementById('user_input-genome')

	species_select.onchange = function() {
		species = species_select.value;
		
		fetch("/openvar/genome/" + species).then(function(response) {
			response.json().then(function(data) {
				let optionHTML = "";

				for (let version of data.genome_versions) {
					optionHTML += '<option value="' + version.value + '">' + version.name + '</option>';
				}

				genome_select.innerHTML = optionHTML;
				
			});
		});
	}
});


//Process upload
$(document).ready( function() {
	$('.submit__upload').click( function(event) {

		event.preventDefault();

		var csrf_token_upload = document.getElementById('file_upload-csrf_token').value;
		$.ajaxSetup({
			beforeSend: function(xhr, settings){
				if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
					xhr.setRequestHeader("X-CSRFToken", csrf_token_upload);
				}
			}
		});

		$("#progressBar").hide();
		$("#upload_errorAlert").hide();
		$("#upload_successAlert").hide();

		if (document.getElementById('user_file_upload_form')['1']['files'].length == 0) {
			$("#upload_errorAlert").text("No file selected. Please select a file to upload.").show();
			$("#upload_successAlert").hide();
		} else {
			var form_data = new FormData();
			form_data.append('file', document.getElementById('user_file_upload_form')['1']['files'][0]);
			$.ajax({
				xhr: function() {
					var myxhr = new window.XMLHttpRequest();
					if (myxhr.upload) {
						console.log('upload progress is supported');
						myxhr.upload.addEventListener("progress", UpdateUploadProgress, false);
						
					} else {
						console.log('upload progress is NOT supported');
					}
					return myxhr;
				},
				
				url:'/openvar/upload_file',
				data: form_data,
				processData: false,
				type: 'POST',
				contentType: false,
				cache: false,
				
				success: function(response) {
					if (response.outcome == 'success') {
						$("#upload_successAlert").text(response.file + " has been successfully uploaded. You may now submit your analysis").show();
						$("#upload_errorAlert").hide();
						$("#user_input-guid").attr('value', response.guid);
					} else {
						$("#upload_errorAlert").text(response.error).show();
						$("#upload_successAlert").hide();
					}
				},
			});
		}
	});
});

function UpdateUploadProgress(evt) {
	$("#progressBar").show();
	if (evt.lengthComputable) {
		var percent = Math.round(evt.loaded / evt.total * 100);
		console.log('Uploaded: ' + percent + ' %')
		$("#progressBar").attr('aria-valuenow', percent).css('width', percent + '%').text(percent + '%');
	}
}
	
//Submit openvar analysis
$(document).ready( function() {
	$('.form__submit__btn').click( function(event) {
		event.preventDefault();
		$('#email_error_msg').hide();
		$('#study_name_error_msg').hide();
		$("#upload_errorAlert").hide();
		$('#user_input-study_name').attr('style', 'border-color: #444;');
		$('#user_input-email').attr('style', 'border-color: #444;');
		
		var csrf_token_submit = document.getElementById('user_input-csrf_token').value;
		$.ajaxSetup({
			beforeSend: function(xhr, settings) {
				if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
					xhr.setRequestHeader("X-CSRFToken", csrf_token_submit);
				}
			}
		});
		
		$.ajax({
			url: '/openvar/opv_submit',
			type: 'POST',
			data: $('#user_input__submitform').serialize(),
			success: function(response) {
				if (response.outcome == 'success') {
					$('#email_error_msg').hide();
					$('#study_name_error_msg').hide();
					$('#user_input-email').attr('style', 'border-color: #ccc;');
					$('#user_input-study_name').attr('style', 'border-color: #ccc;');
					$("#upload_errorAlert").hide();
					if (response.guid == '') {
						$("#upload_errorAlert").text('Please upload a VCF file below.').show();
						$("#upload_successAlert").hide();
					} else {
						$("#OPVsubmit_successAlert").show();
						$('#OPV_results_link').attr('href', response.link);
						console.log(response.link)
					}
				} else {
					console.log(response.data);
					if (response.data.user_input.email) {
						$('#user_input-email').attr('style', 'border-color: red;');
						$('#email_error_msg').text(response.data.user_input.email).show();
					} else if (response.data.user_input.study_name) {
						$('#user_input-study_name').attr('style', 'border-color: red;');
						$('#study_name_error_msg').text(response.data.user_input.study_name).show();
					}
				}
			},
		});


	});
});
