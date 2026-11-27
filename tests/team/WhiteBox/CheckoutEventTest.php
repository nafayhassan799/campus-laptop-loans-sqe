<?php

namespace Tests\team\WhiteBox;

use App\Events\CheckoutableCheckedOut;
use App\Models\Asset;
use App\Models\Location;
use App\Models\User;
use Illuminate\Support\Facades\Event;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class CheckoutEventTest extends TestCase
{
    public static function checkoutDates(): array
    {
        return [
            'historical checkout and explicit operator' => ['2025-06-01 11:30:00', true, true],
            'same-day checkout and authenticated operator' => ['today', false, false],
            'no timestamp and authenticated operator' => [null, false, false],
        ];
    }

    #[DataProvider('checkoutDates')]
    public function test_checkout_persists_one_laptop_and_emits_the_correct_action(
        ?string $timestamp,
        bool $historical,
        bool $explicitOperator,
    ): void {
        $actor = User::factory()->create();
        $authUser = User::factory()->create();
        $home = Location::factory()->create(['id' => 201]);
        $desk = Location::factory()->create(['id' => 202]);
        $borrower = User::factory()->create(['location_id' => $home->id]);
        $asset = Asset::factory()->create(['name' => 'Campus laptop']);
        $this->actingAs($authUser);
        Event::fake([CheckoutableCheckedOut::class]);

        $checkoutAt = $timestamp === 'today' ? date('Y-m-d').' 11:30:00' : $timestamp;
        $location = $explicitOperator ? $desk : $home;
        $this->assertTrue($asset->checkOut(
            $borrower,
            $explicitOperator ? $actor : null,
            $checkoutAt,
            '2090-06-15',
            'Loan counter check',
            'Campus laptop',
            $explicitOperator ? $location->id : null,
        ));

        $stored = $asset->fresh();
        $this->assertSame($borrower->id, $stored->assigned_to);
        $this->assertSame('user', $stored->assignedType());
        $this->assertTrue($stored->checkedOutToUser());
        $this->assertSame($location->id, $stored->location_id);
        $this->assertSame($checkoutAt, $stored->getRawOriginal('last_checkout'));
        $this->assertSame(1, (int) $stored->checkout_counter);

        Event::assertDispatchedTimes(CheckoutableCheckedOut::class, 1);
        Event::assertDispatched(CheckoutableCheckedOut::class, function (CheckoutableCheckedOut $event) use (
            $asset, $borrower, $actor, $authUser, $explicitOperator, $historical
        ): bool {
            return $event->checkoutable->is($asset)
                && $event->checkedOutTo->is($borrower)
                && $event->checkedOutBy?->is($explicitOperator ? $actor : $authUser)
                && $event->note === 'Loan counter check'
                && $event->quantity === 1
                && array_key_exists('action_date', $event->originalValues) === $historical;
        });
    }

    public function test_missing_borrower_leaves_the_asset_untouched(): void
    {
        $asset = Asset::factory()->create(['name' => 'Campus laptop']);
        Event::fake([CheckoutableCheckedOut::class]);

        $this->assertFalse($asset->checkOut(null));
        $this->assertNull($asset->fresh()->assigned_to);
        $this->assertSame('Campus laptop', $asset->fresh()->name);
        Event::assertNotDispatched(CheckoutableCheckedOut::class);
    }
}
