@extends('layouts/default')

{{-- Page title --}}
@section('title')
    {{ trans('admin/hardware/general.checkout') }}
    @parent
@stop

{{-- Page content --}}
@section('content')

    <style>
        .input-group {
            padding-left: 0px !important;
        }

        {{-- SQE A11Y-03: select2 placeholder text (#999 on white, 2.84:1) failed WCAG 1.4.3.
             #6b6b6b on white is 5.33:1. --}}
        #checkout_form .select2-selection__placeholder {
            color: #6b6b6b;
        }
    </style>

    @push('js')
        <script nonce="{{ csrf_token() }}">
            {{-- SQE A11Y-02 and A11Y-04: give every select2 picker on this form the name of its visible
                 <label> (WCAG 4.1.2), and let the "Asset Name" input take its visible label instead of
                 the aria-label="name" the shared field component adds (WCAG 2.5.3 label in name). --}}
            $(function () {
                var $form = $('#checkout_form');
                $form.find('#name').removeAttr('aria-label');
                $form.find('select').each(function (index, select) {
                    var $group = $(select).closest('.form-group');
                    var $label = $group.find('label.control-label, label[for]').first();
                    var $selection = $(select).next('.select2').find('.select2-selection');
                    if (! $selection.length) {
                        return;
                    }
                    if (! $label.length) {
                        // No visible label (e.g. the "after saving" redirect picker): reuse the select's aria-label.
                        $selection.find('.select2-selection__rendered').attr('aria-label', $(select).attr('aria-label'));
                        $selection.attr('aria-label', $(select).attr('aria-label'));
                        return;
                    }
                    var labelId = $label.attr('id') || ('checkout-label-' + (select.id || select.name || index));
                    $label.attr('id', labelId);
                    var $rendered = $selection.find('.select2-selection__rendered');
                    $rendered.attr('aria-labelledby', labelId);
                    $selection.attr('aria-labelledby', labelId + ' ' + $rendered.attr('id'));
                });
            });
        </script>
    @endpush

    <x-container columns="2">
        <x-page-column class="col-md-7">

            <x-form id="checkout_form" route="{{ url()->current() }}">

                <x-box header="{{ trans('admin/hardware/form.tag') }} {{ $asset->asset_tag }}">

                    @if ($asset->company)
                        <x-form.static :label="trans('general.company')">{!! $asset->company->present()->formattedNameLink !!}</x-form.static>
                    @endif

                    @if ($asset->model->category)
                        <x-form.static :label="trans('general.category')">{!! $asset->model->category->present()->formattedNameLink !!}</x-form.static>
                    @endif

                    <x-form.static :label="trans('admin/hardware/form.model')">
                        @if (($asset->model) && ($asset->model->name))
                            {{ $asset->model->name }}
                        @else
                            <span class="text-danger text-bold">
                                <x-icon type="warning" />
                                {{ trans('admin/hardware/general.model_invalid') }}
                            </span>
                            {{ trans('admin/hardware/general.model_invalid_fix') }}
                            <a href="{{ route('hardware.edit', $asset->id) }}">
                                <strong>{{ trans('admin/hardware/general.edit') }}</strong>
                            </a>
                        @endif
                    </x-form.static>

                    <x-form.row
                        :label="trans('admin/hardware/form.name')"
                        :$item
                        name="name"
                    />

                    <x-form.row
                        :label="trans('admin/hardware/form.status')"
                        name="status_id"
                    >
                        <x-slot:input>
                            <x-input.select
                                name="status_id"
                                :options="$statusLabel_list"
                                :selected="$asset->status_id"
                                required
                                style="width: 100%;"
                                aria-label="status_id"
                            />
                        </x-slot:input>
                    </x-form.row>

                    <x-form.checkbox-row
                        name="requestable"
                        :label="trans('admin/hardware/general.requestable')"
                        :item="$asset"
                        data-user-preference-key="snipeit.checkout.requestable_default.{{ auth()->id() ?? 'guest' }}"
                        data-had-old-input="{{ ((bool) old('requestable', false)) || session()->has('_old_input.requestable') ? '1' : '0' }}"
                    />

                    @include ('partials.forms.checkout-selector', ['user_select' => 'true', 'asset_select' => 'true', 'location_select' => 'true'])
                    <x-input.user-select
                        :label="trans('general.user')"
                        name="assigned_user"
                        :selected="old('assigned_user', $checkoutRequest?->user_id)"
                        :companyId="$asset->company_id"
                        :style="(session('checkout_to_type') ?: 'user') == 'user' ? null : 'display: none;'"
                    />
                    <!-- unselect keeps the asset being checked out from being pre-selected in this picker -->
                    @include ('partials.forms.edit.asset-select', ['translated_name' => trans('general.select_asset'), 'fieldname' => 'assigned_asset', 'company_id' => $asset->company_id, 'unselect' => 'true', 'exclude_id' => $asset->id, 'style' => session('checkout_to_type') == 'asset' ? '' : 'display: none;'])
                    @include ('partials.forms.edit.location-select', ['translated_name' => trans('general.location'), 'fieldname' => 'assigned_location', 'company_id' => $asset->company_id, 'style' => session('checkout_to_type') == 'location' ? '' : 'display: none;'])

                        <x-input.location-select
                            :label="trans('general.location')"
                            name="location_id"
                            :selected="old('location_id', $asset->location_id)"
                            :company-id="$asset->company_id"
                        />

                        <x-input.location-select
                            :label="trans('admin/hardware/form.default_location')"
                            name="rtd_location_id"
                            :selected="old('rtd_location_id', $asset->rtd_location_id)"
                            :company-id="$asset->company_id"
                        />

                    <x-form.row
                        :label="trans('admin/hardware/form.checkout_date')"
                        name="checkout_at"
                        type="datetimepicker"
                        :item="$item"
                        :default="date('Y-m-d H:i:s')"
                        input_div_class="col-md-4"
                    />

                    <x-form.row
                        :label="trans('admin/hardware/form.expected_checkin')"
                        name="expected_checkin"
                        type="datetimepicker"
                        :item="$item"
                        :default_now="false"
                        :default="old('expected_checkin', ($checkoutRequest?->end_date ? $checkoutRequest->end_date->toDateString() : ($item->expected_checkin ?? null)))"
                        input_div_class="col-md-4"
                    />

                    <x-form.row
                        :label="trans('general.notes')"
                        name="note"
                    >
                        <x-slot:input>
                            <textarea class="col-md-6 form-control" id="note" name="note" @required($snipeSettings->require_checkinout_notes)>{{ old('note', $asset->note) }}</textarea>
                        </x-slot:input>
                    </x-form.row>

                    <!-- Custom fields -->
                    @include('models/custom_fields_form', [
                        'fieldset' => $asset->custom_fieldset,
                        'defaultValues' => \App\Models\CustomFieldDefault::valuesFor($asset),
                        'show_custom_fields_type' => 'checkout',
                    ])

                    <x-checkout.checkout-notification-callout :item="$asset" :category="$asset->model?->category" />

                    <x-slot:customfooter>
                        <x-redirect_submit_options
                            index_route="hardware.index"
                            :button_label="trans('general.checkout')"
                            :disabled_select="!$asset->model"
                            :options="[
                                'index' => trans('admin/hardware/form.redirect_to_all', ['type' => trans('general.assets')]),
                                'item' => trans('admin/hardware/form.redirect_to_type', ['type' => trans('general.asset')]),
                                'target' => trans('admin/hardware/form.redirect_to_checked_out_to'),
                            ]"
                        />
                    </x-slot:customfooter>

                </x-box>

            </x-form>

        </x-page-column>

        <x-page-column class="col-md-5">
            <x-checkout-request-context :request="$checkoutRequest ?? null" :requestable="$asset" />

            <livewire:checkout-target-panel type="assets" />
        </x-page-column>

    </x-container>
@stop
