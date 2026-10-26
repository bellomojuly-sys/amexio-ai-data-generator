/* Generated from case_model/schema/input.storylines.schema.json by `npm run types`. Do not edit. */

export type Comment = (string | null)
export type Date = (string | null)
export type Rating = string
export type Type = "appraisal"
export type Year = number
export type Appraisals = AppraisalIn[]
export type Employeeid = string
export type Date1 = string
export type Newcontracttype = (string | null)
export type Newhours = (number | null)
export type Newposition = (string | null)
export type Newsalary = (number | string | null)
export type Reason = string
export type Type1 = "contract_change"
export type Course = string
export type Date2 = string
export type Durationdays = number
export type Type2 = "training"
export type Enddate = (string | null)
export type Startdate = string
export type Type3 = "absence"
export type Date3 = string
export type Noticedate = (string | null)
export type Reason1 = string
export type Type4 = "termination"
export type Date4 = string
export type Result = string
export type Type5 = "medical_check"
export type Events = (ContractChangeIn | TrainingIn | AbsenceIn | TerminationIn | MedicalCheckIn | AppraisalIn)[]
export type Storylines = StorylineIn[]

export interface StorylinesIn {
storylines: Storylines
}
/**
 * This interface was referenced by `StorylinesIn`'s JSON-Schema
 * via the `definition` "StorylineIn".
 */
export interface StorylineIn {
appraisals?: Appraisals
employeeId: Employeeid
events?: Events
}
/**
 * In the prompt's ``appraisals`` list (no ``type``), or among the events
 * (``"type": "appraisal"``) once the generator has planned them.
 * 
 * This interface was referenced by `StorylinesIn`'s JSON-Schema
 * via the `definition` "AppraisalIn".
 */
export interface AppraisalIn {
comment?: Comment
date?: Date
rating: Rating
type?: Type
year: Year
}
/**
 * This interface was referenced by `StorylinesIn`'s JSON-Schema
 * via the `definition` "ContractChangeIn".
 */
export interface ContractChangeIn {
date: Date1
newContractType?: Newcontracttype
newHours?: Newhours
newPosition?: Newposition
newSalary?: Newsalary
reason: Reason
type: Type1
}
/**
 * This interface was referenced by `StorylinesIn`'s JSON-Schema
 * via the `definition` "TrainingIn".
 */
export interface TrainingIn {
course: Course
date: Date2
durationDays: Durationdays
type: Type2
}
/**
 * This interface was referenced by `StorylinesIn`'s JSON-Schema
 * via the `definition` "AbsenceIn".
 */
export interface AbsenceIn {
endDate?: Enddate
startDate: Startdate
type: Type3
}
/**
 * This interface was referenced by `StorylinesIn`'s JSON-Schema
 * via the `definition` "TerminationIn".
 */
export interface TerminationIn {
date: Date3
noticeDate?: Noticedate
reason: Reason1
type: Type4
}
/**
 * Added by the generator's rules (every two years), not by the LLM.
 * 
 * This interface was referenced by `StorylinesIn`'s JSON-Schema
 * via the `definition` "MedicalCheckIn".
 */
export interface MedicalCheckIn {
date: Date4
result: Result
type: Type5
}
