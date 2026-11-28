<?php

namespace App\Http\Middleware;

use App\Helpers\Helper;
use App\Models\Setting;
use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use PDOException;
use Symfony\Component\HttpFoundation\Response;

class CheckForSetup
{
    protected $except = [
        '_debugbar*',
        'health',
    ];

    public function handle(Request $request, Closure $next, ?string $guard = null): Response
    {

        /**
         * Skip this middleware for the debugbar and health check
         */
        if ($request->is($this->except)) {
            return $next($request);
        }

        if ($request->is('api/*')) {
            try {
                DB::connection()->getPdo();
            } catch (PDOException $exception) {
                report($exception);

                return $this->apiUnavailable();
            }
        }

        if (Setting::setupCompleted()) {
            if ($request->is('setup*')) {
                return redirect(config('app.url'));
            } else {
                return $next($request);
            }
        } else {
            if ($request->is('api/*')) {
                return $this->apiUnavailable();
            }

            if (! ($request->is('setup*')) && ! ($request->is('.env'))) {
                return redirect(config('app.url').'/setup');
            }

            return $next($request);
        }
    }

    private function apiUnavailable(): JsonResponse
    {
        return response()->json(
            Helper::formatStandardApiResponse('error', null, trans('general.service_temporarily_unavailable')),
            Response::HTTP_SERVICE_UNAVAILABLE
        );
    }
}
