# coding: utf-8
"""
Optimisation tools for pydici staffing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from ortools.sat.python import cp_model


def solve_pdc(consultants, senior_consultants, missions, months, missions_charge, consultants_freetime, predefined_assignment,
              solver_param=None):
    # default value
    if solver_param is None:
        solver_param = {}
    senior_quota = solver_param.get("senior_quota", 20)
    newbie_quota = solver_param.get("newbie_quota", 30)

    # CP-SAT model
    model = cp_model.CpModel()
    # variable we are searching
    staffing = {}  # Per month
    staffing_b = {}  # Bool indicating if consultant is staffed  (ie staffing >0) by month on this mission
    staffing_b_all = {}  # Bool indicating if consultant is staffed on this mission
    staffing_mission_delta = {}  # Delta between proposition and forecast for mission/month
    for consultant in consultants:
        if consultant not in staffing:
            staffing[consultant] = {}
            staffing_b[consultant] = {}
            staffing_b_all[consultant] = {}
        for mission in missions:
            if mission not in staffing[consultant]:
                staffing[consultant][mission] = {}
                staffing_b[consultant][mission] = {}
            for month in months:
                # Define vars
                staffing[consultant][mission][month] = model.NewIntVar(0, consultants_freetime[consultant][month],
                                                                       "staffing[%s,%s,%s]" % (consultant, mission, month))
                staffing_b[consultant][mission][month] = model.NewBoolVar(
                    "staffing_b[%s,%s,%s]" % (consultant, mission, month))
                # Links vars staffing and staffing_b
                model.Add(staffing[consultant][mission][month] > 0).OnlyEnforceIf(staffing_b[consultant][mission][month])
                model.Add(staffing[consultant][mission][month] == 0).OnlyEnforceIf(
                    staffing_b[consultant][mission][month].Not())

            # Define vars staffing_b_all
            staffing_b_all[consultant][mission] = model.NewBoolVar("staffing_b_all[%s,%s]" % (consultant, mission))
            # Links vars staffing and staffing_b_all
            model.Add(sum(staffing[consultant][mission][month] for month in months) > 0).OnlyEnforceIf(
                staffing_b_all[consultant][mission])
            model.Add(sum(staffing[consultant][mission][month] for month in months) == 0).OnlyEnforceIf(
                staffing_b_all[consultant][mission].Not())

    # Define delta between proposition and forecast
    for mission in missions:
        if mission not in staffing_mission_delta:
            staffing_mission_delta[mission] = {}
        for month in months:
            staffing_mission_delta[mission][month] = model.NewIntVar(-1000, 1000,
                                                                     "staffing_mission_delta[%s,%s]" % (mission, month))
            model.Add(
                sum(staffing[consultant][mission][month] for consultant in consultants) >= missions_charge[mission][month] -
                staffing_mission_delta[mission][month])
            model.Add(
                sum(staffing[consultant][mission][month] for consultant in consultants) <= missions_charge[mission][month] +
                staffing_mission_delta[mission][month])

    # Each mission should have a noob for at least 30% and senior for 20% of mission charge each month
    for mission in missions:
        for month in months:
            charge = sum(staffing[consultant][mission][month] for consultant in consultants if consultant not in senior_consultants)
            lead_charge = sum(staffing[consultant][mission][month] for consultant in senior_consultants)
            model.Add((charge + lead_charge) * newbie_quota <= charge * 100)
            model.Add((charge + lead_charge) * senior_quota <= lead_charge * 100)

    # All missions are done, but not overshoot
    for mission in missions:
        s = []
        for month in months:
            s.extend(staffing[consultant][mission][month] for consultant in consultants)

        model.Add(sum(s) == sum(missions_charge[mission].values()))

    # Consultant have limited free time
    for consultant in consultants:
        for month in months:
            model.Add(sum(staffing[consultant][mission][month] for mission in missions) <= consultants_freetime[consultant][
                month])

    # We have predefined assignment
    for mission, assigned_consultants in predefined_assignment.items():
        for consultant in assigned_consultants:
            model.Add(sum(staffing[consultant][mission][month] for month in months) > 0)

    # define score components
    planning_score_items = []
    freetime_score_items = []
    mission_per_people_score_items = []
    people_per_mission_score_items = []

    # respect mission planning
    for mission in missions:
        for month in months:
            if missions_charge[mission][month] > 0:
                # add score if planning is not respected
                planning_score_items.append(staffing_mission_delta[mission][month])
                pass
            else:
                # add twice penalty when charge is used outside forecast (late or too early work)
                planning_score_items.append(2 * sum(staffing[consultant][mission][month] for consultant in consultants))

    for consultant in consultants:
        for month in months:
            # optimise freetime and mission per people only if we have stuff to do
            if sum(missions_charge[mission][month] for mission in missions) > 0:
                # reduce free time for newbies, not for senior consultants
                if consultant not in senior_consultants:
                    charge = sum(staffing[consultant][mission][month] for mission in missions)
                    freetime_score_items.append(consultants_freetime[consultant][month] - charge)
                # limit number of mission per people
                mission_per_people_score_items.append(sum(staffing_b[consultant][mission][month] for mission in missions))

    # limit number of people per mission
    for mission in missions:
        people_per_mission_score_items.append(sum(staffing_b_all[consultant][mission] for consultant in consultants))

    # Optim part
    # Define intermediate score
    planning_score = model.NewIntVar(0, 1000, "planning_score")
    freetime_score = model.NewIntVar(0, 1000, "freetime_score")
    people_per_mission_score = model.NewIntVar(0, 1000, "people_per_mission_score")
    mission_per_people_score = model.NewIntVar(0, 1000, "mission_per_people_score")
    model.Add(planning_score == sum(planning_score_items))
    model.Add(freetime_score == sum(freetime_score_items))
    model.Add(people_per_mission_score == sum(people_per_mission_score_items))
    model.Add(mission_per_people_score == sum(mission_per_people_score_items))

    score = planning_score + freetime_score + mission_per_people_score + people_per_mission_score
    # optimise model to have minimum score
    model.Minimize(score)

    # Solve it
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0 # Limit to 10 secs
    status = solver.Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return (solver, status, [planning_score, freetime_score, people_per_mission_score, mission_per_people_score], staffing)


def display_solver_solution(solver, scores, staffing, consultants, missions, months, missions_charge, consultants_freetime):
    for score in scores:
        print("%s = %s" % (score.Name(), solver.Value(score)))
    print("Total score = %s" % (sum(solver.Value(score) for score in scores)))
    print()
    print("Mis.\tCons.\t" + "\t".join(months))
    for mission in missions:
        print("-" * 35)
        for consultant in consultants:
            charges = "\t ".join(str(solver.Value(staffing[consultant][mission][month])) for month in months)
            print("%s \t %s \t %s" % (mission, consultant, charges))
        print("%s\t All\t" % mission, end="")
        for month in months:
            mission_charge = sum(solver.Value(staffing[consultant][mission][month]) for consultant in consultants)
            print("%s/%s\t" % (mission_charge, missions_charge[mission][month]), end="")
        print()
    print("-" * 35)
    for consultant in consultants:
        print("All\t %s\t" % consultant, end="")
        for month in months:
            consultant_charge = sum(solver.Value(staffing[consultant][mission][month]) for mission in missions)
            print("%s/%s\t" % (consultant_charge, consultants_freetime[consultant][month]), end="")
        print()

