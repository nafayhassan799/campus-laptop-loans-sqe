<?php

namespace App\Http\Requests;

use App\Models\Asset;
use App\Models\Location;
use App\Models\Setting;
use Closure;

class AssetCheckinRequest extends Request
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return ! $this->is('api/*') || $this->user()?->can('checkin', Asset::class);
    }

    /**
     * Get the validation rules that apply to the request.
     */
    public function rules(): array
    {
        $rules = static::rulesArray();
        if (! $this->is('api/*')) {
            return $rules;
        }

        $integerInput = static function (string $attribute, mixed $value, Closure $fail): void {
            if (! is_int($value) && ! is_string($value)) {
                $fail(trans('validation.integer', ['attribute' => str_replace('_', ' ', $attribute)]));
            }
        };

        return $rules + [
            'checkin_at' => 'nullable|date_format:Y-m-d',
            'clear_name' => ['bail', $integerInput, 'in:1'],
            'status_id' => ['bail', 'nullable', $integerInput, 'integer', 'min:1', 'exists_undeleted:status_labels,id'],
            'location_id' => [
                'bail', 'nullable', $integerInput, 'integer', 'min:1',
                static function (string $attribute, mixed $value, Closure $fail): void {
                    if (! Location::whereKey($value)->exists()) {
                        $fail(trans('validation.exists', ['attribute' => 'location']));
                    }
                },
            ],
        ];
    }

    /**
     * Statically-callable rules array so non-FormRequest callers (the MCP
     * CheckinAssetTool, Artisan commands, tests) can validate against the
     * same shape without constructing a Request instance.
     */
    public static function rulesArray(): array
    {
        $settings = Setting::getSettings();

        $rules = [
            'name' => 'nullable|string|max:255',
            'requestable' => 'nullable|boolean',
        ];

        if ($settings->require_checkinout_notes) {
            $rules['note'] = 'string|required';
        }

        return $rules;
    }

    public function response(array $errors)
    {
        return $this->redirector->back()->withInput()->withErrors($errors, $this->errorBag);
    }
}
