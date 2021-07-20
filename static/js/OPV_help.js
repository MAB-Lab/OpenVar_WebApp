// Documentation page

$(document).ready(function() {
	$('.reveal_hide').click( function(event) {
		event.preventDefault()

		var qname = '#' + $(this).attr('name');
		console.log(qname);

		if ( $(qname).css("display") == "none" ) {
			$('#' + qname).attr('style', 'display: block;');
		} else {
			$('#' + qname).attr('style', 'display: none;');
		}

	});
});
