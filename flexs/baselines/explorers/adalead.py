import random

import numpy as np

import flexs
from flexs.utils import sequence_utils as s_utils


class Adalead(flexs.Explorer):
    """
    AdaLead explorer.
    """

    def __init__(
        self,
        model,
        landscape,
        rounds,
        sequences_batch_size,
        model_queries_per_batch,
        starting_sequence,
        alphabet,
        mu=1,
        recomb_rate=0,
        threshold=0.05,
        rho=1,
        log_file=None,
    ):
        name = f"Adalead_mu={mu}_threshold={threshold}"

        super().__init__(
            model,
            landscape,
            name,
            rounds,
            sequences_batch_size,
            model_queries_per_batch,
            starting_sequence,
            log_file,
        )
        self.threshold = threshold
        self.recomb_rate = recomb_rate
        self.alphabet = alphabet
        self.mu = mu  # number of mutations per *sequence*.
        self.rho = rho

    def _recombine_population(self, gen):
        # If only one member of population, can't do any recombining
        if len(gen) == 1:
            return gen

        random.shuffle(gen)
        ret = []
        for i in range(0, len(gen) - 1, 2):
            strA = []
            strB = []
            switch = False
            for ind in range(len(gen[i])):
                if random.random() < self.recomb_rate:
                    switch = not switch

                # putting together recombinants
                if switch:
                    strA.append(gen[i][ind])
                    strB.append(gen[i + 1][ind])
                else:
                    strB.append(gen[i][ind])
                    strA.append(gen[i + 1][ind])

            ret.append("".join(strA))
            ret.append("".join(strB))
        return ret

    def propose_sequences(self, measured_sequences):
        """Generate."""

        measured_sequence_set = set(measured_sequences["sequence"])

        top_fitness = measured_sequences["true_score"].max()
        top_inds = measured_sequences["true_score"] >= top_fitness * (
            1 - np.sign(top_fitness) * self.threshold
        )

        parents = np.resize(
            measured_sequences["sequence"][top_inds].to_numpy(),
            self.sequences_batch_size,
        )

        sequences = {}
        while len(sequences) < self.model_queries_per_batch:
            # generate recombinant mutants
            for i in range(self.rho):
                # @TODO if parents=[], the outer while loops infinitely
                parents = self._recombine_population(parents)

            for root in parents:
                # Here we do rollouts from each parent (root of rollout tree)
                root_fitness = self.model.get_fitness([root]).item()
                node = root

                while len(sequences) < self.model_queries_per_batch:
                    child = s_utils.generate_random_mutant(
                        node, self.mu * 1 / len(node), self.alphabet
                    )

                    # Skip if child has been already been generated before
                    if child in measured_sequence_set or child in sequences:
                        continue

                    # Stop the rollout once the child has worse predicted
                    # fitness than the root of the rollout tree.
                    # Otherwise, set node = child and add child to the list
                    # of sequences to propose.
                    child_fitness = self.model.get_fitness([child]).item()
                    sequences[child] = child_fitness

                    if child_fitness >= root_fitness:
                        node = child
                    else:
                        break

        # We propose the top `self.sequences_batch_size` new sequences we have generated
        new_seqs = np.array(list(sequences.keys()))
        preds = np.array(list(sequences.values()))
        sorted_order = np.argsort(preds)[: -self.sequences_batch_size : -1]

        return new_seqs[sorted_order], preds[sorted_order]
