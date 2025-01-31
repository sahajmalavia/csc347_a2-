import operator
from collections import defaultdict
from typing import List, Set

from bnetbase import Variable, Factor, BN
import csv
import itertools
import functools

DEBUG = False


# def test_factor(f: Factor):
#     # if DEBUG:
#     # if len(f.scope) != 0:
#     #     s = functools.reduce(operator.mul, [v.domain_size() for v in f.scope])
#     #         # print(f)
#     #     assert len(f.values) <= s
#     pass

def multiply(factor_list: List[Factor]) -> Factor:
    """
    Multiply a list of factors together.
    Do not modify any of the input factors.

    :param factor_list: a list of Factor objects.
    :return: a new Factor object resulting from multiplying all the factors in factor_list.
    """
    combined_f = factor_list[0]
    for factor in factor_list[1:]:
        combined_f = multiply2(combined_f, factor)
    return combined_f


def multiply2(factor_one: Factor, factor_two: Factor) -> Factor:
    """
    Multiply two factors together.

    :param factor_one: the first Factor object.
    :param factor_two: the second Factor object.
    :return: a new Factor object resulting from multiplying the two input factors.
    """
    # Merge the scopes
    new_scope = list(factor_one.scope)
    for var in factor_two.scope:
        if var not in new_scope:
            new_scope.append(var)

    # Prepare domains for all variables in the new scope
    domains = [var.domain() for var in new_scope]

    # Initialize list to hold assignments and their multiplied values
    new_assignments = []

    # Generate all possible assignments over the new scope
    for assignment in itertools.product(*domains):
        # Create a mapping from variable to value for the current assignment
        assignment_dict = dict(zip(new_scope, assignment))

        # Extract assignments relevant to each factor
        f1_assignment = tuple(assignment_dict[var] for var in factor_one.scope)
        f2_assignment = tuple(assignment_dict[var] for var in factor_two.scope)

        # Retrieve values from each factor
        f1_value = factor_one.get_value(f1_assignment)
        f2_value = factor_two.get_value(f2_assignment)

        # Multiply the values
        multiplied_value = f1_value * f2_value

        # Append the assignment and its multiplied value
        new_assignments.append(list(assignment) + [multiplied_value])

    # Create the new factor with the merged scope
    combined_factor = Factor(f'({factor_one.name} * {factor_two.name})', new_scope)

    # Add the assignments and their values to the new factor
    combined_factor.add_values(new_assignments)

    return combined_factor

# def multiply_two_factors(f1: Factor, f2: Factor) -> Factor:
#     new_scope = f1.get_scope()
#     # get common variable indices
#     f1_common_idx, f2_common_idx = [], []
#     for i, v1 in enumerate(f1.get_scope()):
#         for j, v2 in enumerate(f2.get_scope()):
#             if v1 == v2:
#                 f1_common_idx.append(i)
#                 f2_common_idx.append(j)
#     # append all variables that are not in f1.scope
#     for v in f2.get_scope():
#         if v in new_scope:
#             continue
#         new_scope.append(v)
#     # find all assignments of f1 and f2
#     f1_all_assignments = tuple(itertools.product(*(v.domain()
#                                                    for v in
#                                                    f1.get_scope())))
#     f2_all_assignments = tuple(itertools.product(*(v.domain()
#                                                    for v in
#                                                    f2.get_scope())))
#     new_assignments = []
#     for f1_a in f1_all_assignments:
#         for f2_a in f2_all_assignments:
#             if any(f1_a[f1_common_idx[i]] != f2_a[f2_common_idx[i]]
#                    for i in range(len(f1_common_idx))):
#                 continue
#             # if all common vars are equal
#             res = f1.get_value(f1_a) * f2.get_value(f2_a)
#             new_a = list(f1_a) + \
#                     [f2_a[i] for i in range(len(f2.get_scope()))
#                      if i not in f2_common_idx] + \
#                     [res]
#             new_assignments.append(new_a)
#     new_f = Factor(f'({f1.name} * {f2.name})', new_scope)
#     new_f.add_values(new_assignments)
#     return new_f
# def multiply(factors: List[Factor]) -> Factor:
#     """
#     Factors is a list of factor objects.
#     Return a new factor that is the product of the factors in Factors.
#     @return a factor
#     """
#     res_f = factors[0]
#     for i in range(1, len(factors)):
#         res_f = multiply_two_factors(res_f, factors[i])
#     if DEBUG:
#         assert res_f
#         # test_factor(res_f)
#     return res_f


def restrict(f: Factor, var: Variable, value) -> Factor:
    """
    f is a factor, var is a Variable, and value is a value from var.domain.
    Return a new factor that is the restriction of f by this var = value.
    Don't change f! If f has only one variable its restriction yields a
    constant factor.
    @return a factor
    """
    values, scope = f.values, f.get_scope()
    var_idx = scope.index(var)
    value_idx = var.value_index(value)
    # if len(scope) == 1:
    #     restricted_f = Factor(f'r({f.name}, {var.name}={value})', scope)
    #     restricted_f.values = [f.values[value_idx]]
    #     return restricted_f
    # units
    unit = 1
    for i in range(var_idx):
        unit *= scope[i].domain_size()
    unit_size = len(values) // unit
    # gap between values of var
    gap = 1
    for i in range(var_idx + 1, len(scope)):
        gap *= scope[i].domain_size()
    start = value_idx * gap
    new_values = []
    for i in range(0, len(values), unit_size):
        new_values.extend(values[i + j] for j in range(start, start + gap))
    scope.pop(var_idx)
    restricted_f = Factor(f'r({f.name}, {var.name}={value})', scope)
    restricted_f.values = new_values
    # if DEBUG:
    #     test_factor(restricted_f)
    return restricted_f


def sum_out(f: Factor, var: Variable) -> Factor:
    """
    f is a factor, var is a Variable.
    Return a new factor that is the result of summing var out of f, by summing
    the function generated by the product over all values of var.
    @return a factor
    """
    values, scope = f.values, f.get_scope()
    var_idx = scope.index(var)
    # gap between values of var
    gap = 1
    for i in range(var_idx + 1, len(scope)):
        gap *= scope[i].domain_size()
    new_values = []
    offset = 0
    while offset < len(values):
        # sum out var for one unit
        new_values.extend(
            sum(values[i + j * gap] for j in range(var.domain_size()))
            for i in range(offset, gap + offset)
        )
        offset += gap * var.domain_size()
    scope.pop(var_idx)
    new_f = Factor(f's({f.name}, {var.name})', scope)
    new_f.values = new_values
    # if DEBUG:
    #     test_factor(new_f)
    return new_f


def normalize2(nums: List[float]) -> List[float]:
    """
    num is a list of numbers. Return a new list of numbers where the new
    numbers sum to 1, i.e., normalize the input numbers.
    @return a normalized list of numbers
    """
    norm = sum(nums)
    if DEBUG:
        import math
        assert math.isclose(sum([num / norm for num in nums]), 1)
    return [num / norm for num in nums]


def normalize(f: Factor) -> Factor:
    """
    f is a factor. Return a new factor that is the normalized version of f.
    @return a factor
    """
    f.values = normalize2(f.values)
    return f


def get_eliminated_scope(scopes: List[Set[Variable]], var: Variable):
    related = [s for s in scopes if var in s]
    # because we need to multiply them and then sum out var, so the resulting
    # scope is the union of all variables in related - var
    res = set()
    for scope in related:
        res.update(scope)
    if var in res:
        res.remove(var)
    return res, related


def min_fill_ordering(factors: List[Factor], query_var: Variable) \
        -> List[Variable]:
    """
    Factors is a list of factor objects, QueryVar is a query variable.
    Compute an elimination order given list of factors using the min fill
    heuristic.
    Variables in the list will be derived from the scopes of the factors in
    Factors.
    Order the list such that the first variable in the list generates the
    smallest factor upon elimination.
    The QueryVar must NOT part of the returned ordering list.
    @return a list of variables
    """
    scopes = [set(f.get_scope()) for f in factors]
    hidden_variables = set(functools.reduce(set.union, scopes))
    hidden_variables.remove(query_var)
    res = []
    while hidden_variables:
        it = iter(hidden_variables)
        # the var that generates the smallest factor in the current scopes
        min_var = next(it)
        min_scope, related_scopes = get_eliminated_scope(scopes, min_var)
        for hv in it:
            temp_scope, temp_scopes = get_eliminated_scope(scopes, hv)
            # if we have found a var that generates a smaller factor
            if len(temp_scope) < len(min_scope):
                min_var = hv
                min_scope = temp_scope
        res.append(min_var)
        hidden_variables.remove(min_var)
        # we now eliminated min_var, so we need to remove all related scopes
        # and add the scope generated by min_var
        scopes = [s for s in scopes if s not in related_scopes]
        scopes.append(min_scope)
    return res


# def ve(net: BN, query_var: Variable, evidence_vars: List[Variable]) \
#         -> Factor:
#     """
#     Input: Net---a BN object (a Bayes Net)
#            QueryVar---a Variable object (the variable whose distribution
#                       we want to compute)
#            EvidenceVars---a LIST of Variable objects. Each of these
#                           variables has had its evidence set to a particular
#                           value from its domain using set_evidence.
#      VE returns a distribution over the values of QueryVar, i.e., a list
#      of numbers, one for every value in QueryVar's domain. These numbers
#      sum to one, and the i'th number is the probability that QueryVar is
#      equal to its i'th value given the setting of the evidence
#      variables. For example if QueryVar = A with Dom[A] = ['a', 'b',
#      'c'], EvidenceVars = [B, C], and we have previously called
#      B.set_evidence(1) and C.set_evidence('c'), then VE would return a
#      list of three numbers. E.g. [0.5, 0.24, 0.26]. These numbers would
#      mean that Pr(A='a'|B=1, C='c') = 0.5 Pr(A='a'|B=1, C='c') = 0.24
#      Pr(A='a'|B=1, C='c') = 0.26
#      @return a list of probabilities, one for each item in the domain of the
#      QueryVar
#      """
#     factors = net.factors()
#     # restrict the factors
#     for evidence_var in evidence_vars:
#         for i in range(len(factors)):
#             if evidence_var not in factors[i].get_scope():
#                 continue
#             factors[i] = restrict(factors[i], evidence_var,
#                                   evidence_var.get_evidence())
#     # eliminate hidden variables
#     hidden_vars = min_fill_ordering(factors, query_var)
#     for hidden_var in hidden_vars:
#         # multiply all factors that contain hidden_var
#         # find all factors that contain hidden_var
#         related_factors = [f for f in factors if hidden_var in f.get_scope()]
#         if not related_factors:
#             continue
#         # multiply
#         res_factor = multiply(related_factors)
#         # sum out hidden_var from the resulting factor
#         res_factor = sum_out(res_factor, hidden_var)
#         factors.append(res_factor)
#         # remove those factors that contain hidden var
#         factors = [f for f in factors if f not in related_factors]
#     # multiply the remaining factors
#
#     res = multiply(factors)
#     return normalize(res)
def ve(bayes_net: BN, query_variable: Variable, evidence_variables: List[Variable]) -> Factor:
    """
    Performs variable elimination on the given Bayesian network to compute
    the distribution over the query variable given evidence.

    Args:
        bayes_net: The Bayesian network object.
        query_variable: The variable whose distribution we want to compute.
        evidence_variables: A list of Variable objects with evidence set.

    Returns:
        A normalized Factor representing the distribution over the query variable.
    """
    # Step 1: Retrieve all factors from the Bayesian network
    factors = bayes_net.factors()

    # Step 2: Restrict factors based on the evidence
    for evidence_var in evidence_variables:
        evidence_value = evidence_var.get_evidence()
        for idx in range(len(factors)):
            factor = factors[idx]
            if evidence_var in factor.get_scope():
                # Restrict the factor to the evidence value
                factors[idx] = restrict(factor, evidence_var, evidence_value)

    # Step 3: Determine the elimination order using the min-fill heuristic
    # Collect all variables in the factors' scopes, excluding the query variable
    scopes = [set(factor.get_scope()) for factor in factors]
    all_variables = set().union(*scopes)
    hidden_variables = all_variables - {query_variable}

    elimination_order = []

    while hidden_variables:
        min_fill_variable = None
        min_fill_scope = None
        min_fill_size = float('inf')
        min_related_scopes = []

        # Evaluate each hidden variable to find the one with minimal fill-in
        for var in hidden_variables:
            # Find all scopes containing the variable
            related_scopes = [scope for scope in scopes if var in scope]
            # Compute the union of these scopes (excluding the variable to eliminate)
            combined_scope = set().union(*related_scopes) - {var}
            fill_size = len(combined_scope)

            # Select the variable with the smallest resulting scope
            if fill_size < min_fill_size:
                min_fill_variable = var
                min_fill_scope = combined_scope
                min_fill_size = fill_size
                min_related_scopes = related_scopes

        # Update the elimination order and remove the variable from hidden_variables
        elimination_order.append(min_fill_variable)
        hidden_variables.remove(min_fill_variable)

        # Update the scopes by removing related scopes and adding the new combined scope
        scopes = [scope for scope in scopes if scope not in min_related_scopes]
        scopes.append(min_fill_scope)

    # Step 4: Eliminate hidden variables according to the elimination order
    for eliminate_var in elimination_order:
        # Identify factors that include the variable to eliminate
        factors_to_multiply = [factor for factor in factors if eliminate_var in factor.get_scope()]

        if not factors_to_multiply:
            continue  # No factors to process for this variable

        # Multiply all relevant factors together
        product_factor = multiply(factors_to_multiply)

        # Sum out the variable to eliminate
        summed_factor = sum_out(product_factor, eliminate_var)

        # Update the factors list: remove old factors and add the new one
        factors = [factor for factor in factors if factor not in factors_to_multiply]
        factors.append(summed_factor)

    # Step 5: Multiply the remaining factors
    final_factor = multiply(factors)

    # Step 6: Normalize the final factor
    normalized_factor = normalize(final_factor)

    return normalized_factor


def naive_bayes_model(s) -> BN:
    """
    NaiveBayesModel returns a BN that is a Naive Bayes model that
    represents the joint distribution of value assignments to
    variables in the Adult Dataset from UCI.  Remember a Naive Bayes model
    assumes P(X1, X2,.... XN, Class) can be represented as
    P(X1|Class)*P(X2|Class)* .... *P(XN|Class)*P(Class).
    When you generated your Bayes Net, assume that the values
    in the SALARY column of the dataset are the CLASS that we want to predict.
    @return a BN that is a Naive Bayes model and which represents the Adult
    Dataset.
    """
    # READ IN THE DATA
    input_data = []
    with open(s, newline='') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader, None)  # skip header row
        # each row is a list of str
        for row in reader:
            input_data.append(row)

    # DOMAIN INFORMATION REFLECTS ORDER OF COLUMNS IN THE DATA SET
    variable_domains = {
        "Work": ['Not Working', 'Government', 'Private', 'Self-emp'],
        "Education": [
            '<Gr12', 'HS-Graduate', 'Associate', 'Professional', 'Bachelors',
            'Masters', 'Doctorate'],
        "Occupation": [
            'Admin', 'Military', 'Manual Labour', 'Office Labour', 'Service',
            'Professional'],
        "MaritalStatus": ['Not-Married', 'Married', 'Separated', 'Widowed'],
        "Relationship": [
            'Wife', 'Own-child', 'Husband', 'Not-in-family', 'Other-relative',
            'Unmarried'],
        "Race": [
            'White', 'Black', 'Asian-Pac-Islander', 'Amer-Indian-Eskimo',
            'Other'],
        "Gender": ['Male', 'Female'],
        "Country": [
            'North-America', 'South-America', 'Europe', 'Asia', 'Middle-East',
            'Carribean'],
        "Salary": ['<50K', '>=50K']
    }
    # create variables
    WORK = Variable('work', variable_domains['Work'])
    EDUCATION = Variable('education', variable_domains['Education'])
    MARTIAL_STATUS = Variable('martial_status',
                              variable_domains['MaritalStatus'])
    OCCUPATION = Variable('occupation', variable_domains['Occupation'])
    RELATIONSHIP = Variable('relationship', variable_domains['Relationship'])
    RACE = Variable('race', variable_domains['Race'])
    GENDER = Variable('gender', variable_domains['Gender'])
    COUNTRY = Variable('country', variable_domains['Country'])
    SALARY = Variable('salary', variable_domains['Salary'])

    # create factors
    f_work = Factor('work', [WORK, SALARY])
    f_education = Factor('education', [EDUCATION, SALARY])
    f_martial_status = Factor('martial_status', [MARTIAL_STATUS, SALARY])
    f_occupation = Factor('occupation', [OCCUPATION, SALARY])
    f_relationship = Factor('relationship', [RELATIONSHIP, SALARY])
    f_race = Factor('race', [RACE, SALARY])
    f_gender = Factor('gender', [GENDER, SALARY])
    f_country = Factor('country', [COUNTRY, SALARY])
    f_salary = Factor('salary', [SALARY])
    factors = [f_work, f_education, f_martial_status, f_occupation,
               f_relationship, f_race, f_gender, f_country]

    # salary count
    n = len(input_data)
    salary_count = {'<50K': 0., '>=50K': 0.}
    for w, e, m, o, re, ra, g, c, s in input_data:
        salary_count[s] += 1
    # other
    other_count = [defaultdict(float) for _ in range(8)]
    for w, e, m, o, re, ra, g, c, s in input_data:
        other_count[0][(w, s)] += 1
        other_count[1][(e, s)] += 1
        other_count[2][(m, s)] += 1
        other_count[3][(o, s)] += 1
        other_count[4][(re, s)] += 1
        other_count[5][(ra, s)] += 1
        other_count[6][(g, s)] += 1
        other_count[7][(c, s)] += 1
    for i in range(8):
        values = [[key[0], key[1], value / salary_count[key[1]]] for key, value in
                  other_count[i].items()]
        factors[i].add_values(values)
    # init salary factor
    f_salary.add_values([[key, value / n] for key, value in salary_count.items()])
    factors.append(f_salary)
    # create BN
    bn = BN('bayes_net',
            [WORK, EDUCATION, MARTIAL_STATUS, OCCUPATION, RELATIONSHIP,
             RACE, GENDER, COUNTRY, SALARY],
            factors)
    return bn



def explore(net: BN, question: int) -> float:
    """
    Input: Net---a BN object (a Bayes Net)
    question---an integer indicating the question in HW4 to be calculated.
    Options are:
    1. What percentage of the women in the data set end up with a
       P(S=">=$50K"|E1) that is strictly greater than P(S=">=$50K"|E2)?
    2. What percentage of the men in the data set end up with a
       P(S=">=$50K"|E1) that is strictly greater than P(S=">=$50K"|E2)?
    3. What percentage of the women in the data set with P(S=">=$50K"|E1) > 0.5
       actually have a salary over $50K?
    4. What percentage of the men in the data set with P(S=">=$50K"|E1) > 0.5
       actually have a salary over $50K?
    5. What percentage of the women in the data set are assigned a
       P(Salary=">=$50K"|E1) > 0.5, overall?
    6. What percentage of the men in the data set are assigned a
       P(Salary=">=$50K"|E1) > 0.5, overall?
    @return a percentage (between 0 and 100)
    """
    (WORK, EDUCATION, MARITAL_STATUS, OCCUPATION, RELATIONSHIP, RACE, GENDER,
     COUNTRY, SALARY) = net.variables()
    E1 = [WORK, OCCUPATION, EDUCATION, RELATIONSHIP]
    E2 = [WORK, OCCUPATION, EDUCATION, RELATIONSHIP, GENDER]

    test_data = []
    with open('data/adult-test.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader, None)  # skip header row
        # each row is a list of str
        for row in reader:
            test_data.append(row)
    n = len(test_data)
    n_man = 0
    n_woman = 0
    for w, e, m, o, re, ra, g, c, s in test_data:
        if g == 'Male':
            n_man += 1
        else:
            n_woman += 1
    # assert n_man + n_woman == n

    if question == 1:
        count = 0
        for w, e, m, o, re, ra, g, c, s in test_data:
            if g != 'Female':
                continue
            WORK.set_evidence(w)
            OCCUPATION.set_evidence(o)
            EDUCATION.set_evidence(e)
            RELATIONSHIP.set_evidence(re)
            GENDER.set_evidence(g)
            # p1 = ve(net, SALARY, E1)
            # p2 = ve(net, SALARY, E2)
            p1 = ve(net, SALARY, E1).values[1]
            p2 = ve(net, SALARY, E2).values[1]

            if p1 > p2:
                count += 1

        return count / n_woman * 100
    elif question == 2:
        count = 0
        for w, e, m, o, re, ra, g, c, s in test_data:
            if g != 'Male':
                continue
            WORK.set_evidence(w)
            OCCUPATION.set_evidence(o)
            EDUCATION.set_evidence(e)
            RELATIONSHIP.set_evidence(re)
            GENDER.set_evidence(g)

            p1 = ve(net, SALARY, E1).values[1]
            p2 = ve(net, SALARY, E2).values[1]

            if p1 > p2:
                count += 1

        return count / n_man * 100
    elif question == 3:
        count = 0
        total = 0
        for w, e, m, o, re, ra, g, c, s in test_data:
            if g != 'Female':
                continue
            WORK.set_evidence(w)
            OCCUPATION.set_evidence(o)
            EDUCATION.set_evidence(e)
            RELATIONSHIP.set_evidence(re)

            p = ve(net, SALARY, E1).values[1]

            if p > 0.5:
                total += 1
                count += int(s == '>=50K')
        return count / total * 100
    elif question == 4:
        count = 0
        total = 0
        for w, e, m, o, re, ra, g, c, s in test_data:
            if g != 'Male':
                continue
            WORK.set_evidence(w)
            OCCUPATION.set_evidence(o)
            EDUCATION.set_evidence(e)
            RELATIONSHIP.set_evidence(re)

            p = ve(net, SALARY, E1).values[1]

            if p > 0.5:
                total += 1
                count += int(s == '>=50K')
        return count / total * 100
    elif question == 5:
        count = 0
        for w, e, m, o, re, ra, g, c, s in test_data:
            if g != 'Female':
                continue
            WORK.set_evidence(w)
            OCCUPATION.set_evidence(o)
            EDUCATION.set_evidence(e)
            RELATIONSHIP.set_evidence(re)

            p = ve(net, SALARY, E1).values[1]

            if p > 0.5:
                count += 1

        return count / n_woman * 100
    elif question == 6:
        count = 0
        for w, e, m, o, re, ra, g, c, s in test_data:
            if g != 'Male':
                continue
            WORK.set_evidence(w)
            OCCUPATION.set_evidence(o)
            EDUCATION.set_evidence(e)
            RELATIONSHIP.set_evidence(re)

            p = ve(net, SALARY, E1).values[1]

            if p > 0.5:
                count += 1
        return count / n_man * 100


if __name__ == '__main__':
    nb = naive_bayes_model('data/adult-train.csv')
    for i in range(1, 7):
        print("explore(nb,{}) = {}".format(i, explore(nb, i)))