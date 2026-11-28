<style>
    #{{ $formId }} .select2-selection__placeholder {
        color: #6b6b6b;
    }
</style>

@push('js')
    <script nonce="{{ csrf_token() }}">
        $(function () {
            var formId = @json($formId);
            var $form = $(document.getElementById(formId));

            $form.find('#name').removeAttr('aria-label');
            $form.find('select').each(function (index, select) {
                var $select = $(select);
                var $label = $select.closest('.form-group').find('label.control-label, label[for]').first();
                var $selection = $select.next('.select2').find('.select2-selection');
                var $rendered = $selection.find('.select2-selection__rendered');

                if (! $selection.length) {
                    return;
                }
                if (! $label.length) {
                    var label = $select.attr('aria-label');
                    if (label) {
                        $rendered.add($selection).attr('aria-label', label);
                    }
                    return;
                }
                var labelId = $label.attr('id') || (formId + '-label-' + (select.id || select.name || index));
                $label.attr('id', labelId);
                $rendered.attr('aria-labelledby', labelId);
                $selection.attr('aria-labelledby', labelId + ' ' + $rendered.attr('id'));
            });
        });
    </script>
@endpush
