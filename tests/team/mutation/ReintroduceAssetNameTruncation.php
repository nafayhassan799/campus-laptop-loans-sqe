<?php

namespace Sqe\Mutation;

use Infection\Mutator\Definition;
use Infection\Mutator\Mutator;
use Infection\Mutator\MutatorCategory;
use PhpParser\Node;
use PhpParser\Node\Arg;
use PhpParser\Node\Expr\Assign;
use PhpParser\Node\Expr\BinaryOp\Identical;
use PhpParser\Node\Expr\ConstFetch;
use PhpParser\Node\Expr\FuncCall;
use PhpParser\Node\Expr\PropertyFetch;
use PhpParser\Node\Expr\Ternary;
use PhpParser\Node\Expr\Variable;
use PhpParser\Node\Identifier;
use PhpParser\Node\Name;
use PhpParser\Node\Scalar\Int_;

final class ReintroduceAssetNameTruncation implements Mutator
{
    public function canMutate(Node $node): bool
    {
        return $node instanceof Assign
            && $node->expr instanceof Variable
            && $node->expr->name === 'name'
            && $node->var instanceof PropertyFetch
            && $node->var->name instanceof Identifier
            && $node->var->name->toString() === 'name'
            && $node->var->var instanceof Variable
            && $node->var->var->name === 'this';
    }

    public function mutate(Node $node): iterable
    {
        $changed = clone $node;
        $null = new ConstFetch(new Name('null'));
        $changed->expr = new Ternary(
            new Identical($node->expr, $null),
            $null,
            new FuncCall(new Name('mb_substr'), [new Arg($node->expr), new Arg(new Int_(0)), new Arg(new Int_(191))]),
        );
        yield $changed;
    }

    public static function getDefinition(): Definition
    {
        return new Definition(
            'Reintroduce the truncation previously caused by the 191-character database column.',
            MutatorCategory::ORTHOGONAL_REPLACEMENT,
            'Assert the exact persisted name after checking out a laptop.',
            '$this->name = $name becomes $this->name = $name === null ? null : mb_substr($name, 0, 191)',
        );
    }

    public function getName(): string
    {
        return self::class;
    }
}
