/* Generated from case_model/schema/input.employees.schema.json by `npm run types`. Do not edit. */

export type Absenceservice = (string | null)
export type Directorname = (string | null)
export type Employername = string
export type Examiner = (string | null)
export type Trainingprovider = (string | null)
/**
 * @minItems 1
 */
export type Employees = [EmployeeIn, ...(EmployeeIn)[]]
export type Contracttype = string
export type Department = string
export type Firstname = string
export type Hiredate = string
export type Hoursperweek = number
export type Ismanager = boolean
export type Lastname = string
export type Managername = (string | null)
export type Position = string
export type Startsalary = (number | string)

export interface EmployeesIn {
company: CompanyIn
employees: Employees
}
/**
 * This interface was referenced by `EmployeesIn`'s JSON-Schema
 * via the `definition` "CompanyIn".
 */
export interface CompanyIn {
absenceService?: Absenceservice
directorName?: Directorname
employerName: Employername
examiner?: Examiner
trainingProvider?: Trainingprovider
}
/**
 * This interface was referenced by `EmployeesIn`'s JSON-Schema
 * via the `definition` "EmployeeIn".
 */
export interface EmployeeIn {
contractType: Contracttype
department: Department
firstName: Firstname
hireDate: Hiredate
hoursPerWeek: Hoursperweek
isManager?: Ismanager
lastName: Lastname
managerName?: Managername
position: Position
startSalary: Startsalary
}
