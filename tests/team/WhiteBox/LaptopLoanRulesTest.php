<?php

namespace Tests\team\WhiteBox;

use App\Models\Asset;
use App\Models\Statuslabel;
use App\Models\User;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class LaptopLoanRulesTest extends TestCase
{
    public static function nameBoundaries(): array
    {
        return ['below' => [254, true], 'at' => [255, true], 'above' => [256, false]];
    }

    #[DataProvider('nameBoundaries')]
    public function test_checkout_name_boundaries_preserve_state(int $length, bool $accepted): void
    {
        $borrower = User::factory()->create();
        $asset = Asset::factory()->create(['name' => 'Lab laptop']);
        $name = str_repeat('L', $length);
        $due = '2090-04-15';
        $this->actingAsForApi(User::factory()->checkoutAssets()->create());

        $this->postJson(route('api.asset.checkout', $asset), [
            'checkout_to_type' => 'user',
            'assigned_user' => $borrower->id,
            'name' => $name,
            'expected_checkin' => $due,
        ])->assertOk()->assertJsonPath('status', $accepted ? 'success' : 'error');

        $asset->refresh();
        $this->assertSame($accepted ? $name : 'Lab laptop', $asset->name);
        $this->assertSame($accepted ? $borrower->id : null, $asset->assigned_to);
        $this->assertSame($accepted ? $due : null, $asset->expected_checkin?->toDateString());
        $this->assertSame($accepted ? ['checkout'] : [], $this->loanHistory($asset));
    }

    public function test_unavailable_laptop_preserves_its_original_loan(): void
    {
        $borrower = User::factory()->create();
        $otherBorrower = User::factory()->create();
        $asset = Asset::factory()->create();
        $this->actingAsForApi(User::factory()->checkoutAssets()->create());

        $checkout = route('api.asset.checkout', $asset);
        $this->postJson($checkout, [
            'checkout_to_type' => 'user',
            'assigned_user' => $borrower->id,
            'expected_checkin' => '2090-05-20',
        ])->assertOk()->assertJsonPath('status', 'success');
        $this->postJson($checkout, [
            'checkout_to_type' => 'user',
            'assigned_user' => $otherBorrower->id,
        ])->assertOk()->assertJsonPath('status', 'error');

        $asset->refresh();
        $this->assertSame($borrower->id, $asset->assigned_to);
        $this->assertSame('2090-05-20', $asset->expected_checkin->toDateString());
        $this->assertSame(['checkout'], $this->loanHistory($asset));
    }

    public static function returnStatuses(): array
    {
        return ['available for re-loan' => [true], 'held for repair' => [false]];
    }

    #[DataProvider('returnStatuses')]
    public function test_return_clears_the_loan_and_respects_the_selected_status(bool $deployable): void
    {
        $borrower = User::factory()->create();
        $status = $deployable ? Statuslabel::factory()->rtd()->create() : Statuslabel::factory()->outForRepair()->create();
        $asset = Asset::factory()->create([
            'assigned_to' => $borrower->id,
            'assigned_type' => User::class,
            'expected_checkin' => '2090-05-20',
        ]);
        $this->actingAsForApi(User::factory()->checkinAssets()->checkoutAssets()->create());

        $checkin = route('api.asset.checkin', $asset);
        $this->postJson($checkin, ['status_id' => $status->id])
            ->assertOk()->assertJsonPath('status', 'success');
        $asset->refresh();
        $this->assertNull($asset->assigned_to);
        $this->assertNull($asset->assigned_type);
        $this->assertNull($asset->expected_checkin);
        $this->assertSame($status->id, $asset->status_id);
        $this->assertSame(['checkin from'], $this->loanHistory($asset));

        $this->postJson($checkin)->assertOk()->assertJsonPath('status', 'error');
        $this->postJson($checkin, ['status_id' => $status->id])
            ->assertOk()->assertJsonPath('status', 'success');
        $this->assertSame(['checkin from'], $this->loanHistory($asset));

        $this->postJson(route('api.asset.checkout', $asset), [
            'checkout_to_type' => 'user', 'assigned_user' => $borrower->id,
        ])->assertOk()->assertJsonPath('status', $deployable ? 'success' : 'error');
        $asset->refresh();
        $this->assertSame($deployable ? $borrower->id : null, $asset->assigned_to);
        $this->assertSame($deployable ? ['checkin from', 'checkout'] : ['checkin from'], $this->loanHistory($asset));
    }

    public function test_reviewer_can_view_but_cannot_change_a_loan(): void
    {
        $borrower = User::factory()->create();
        $available = Asset::factory()->create();
        $loaned = Asset::factory()->create(['assigned_to' => $borrower->id, 'assigned_type' => User::class]);
        $this->actingAsForApi(User::factory()->viewAssets()->create());

        $this->getJson("/api/v1/hardware/{$loaned->id}")->assertOk()->assertJsonPath('id', $loaned->id);
        $this->postJson(route('api.asset.checkout', $available), [
            'checkout_to_type' => 'user', 'assigned_user' => $borrower->id,
        ])->assertForbidden();
        $this->postJson(route('api.asset.checkin', $loaned))->assertForbidden();

        $this->assertNull($available->fresh()->assigned_to);
        $this->assertSame($borrower->id, $loaned->fresh()->assigned_to);
        $this->assertSame([], $this->loanHistory($available));
        $this->assertSame([], $this->loanHistory($loaned));
    }

    private function loanHistory(Asset $asset): array
    {
        return $asset->assetlog()
            ->whereIn('action_type', ['checkout', 'checkin from'])
            ->reorder('id')
            ->pluck('action_type')
            ->all();
    }
}
