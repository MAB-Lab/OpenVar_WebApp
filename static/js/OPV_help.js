// Documentation page

$(document).ready(function() {
	$('.reveal_hide').click( function(event) {
		event.preventDefault()
		var qname = event.target.name;
		if ( $('#' + qname).is(":hidden") ) {
			$('#' + qname).attr('style', 'display: block;');
		} else {
			$('#' + qname).attr('style', 'display: none;');
		}

	});
});
