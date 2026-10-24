/* Generated from case_model/schema/case.schema.json by `npm run types`. Do not edit. */

export type CaseNumber = string
export type EventId = (string | null)
export type Id = string
export type Confidential = boolean
export type DocumentDate = string
export type DocumentType = ("employment_contract" | "payslip" | "medical_check" | "performance_appraisal" | "training_certificate" | "contract_amendment" | "annual_income_statement" | "absence_report" | "termination_letter")
export type EmployeeId = string
export type Tags = string[]
export type ParticipantIds = string[]
export type Text = (string | null)
export type Type = ("employment_contract" | "payslip" | "medical_check" | "performance_appraisal" | "training_certificate" | "contract_amendment" | "annual_income_statement" | "absence_report" | "termination_letter")
export type Description = (string | null)
export type EmployeeNumber = string
export type FolderTitle = (string | null)
export type ContractType = ("Permanent" | "Temporary")
export type Department = string
export type Hours = number
export type OrganisationId = string
export type PersonaId = string
export type Position = string
export type Amount = string
export type Currency = string
export type StartDate = string
export type Employments = Employment[]
export type Date = string
export type Id1 = string
export type Label = (string | null)
export type ParticipantIds1 = string[]
export type Summary = (string | null)
export type Type1 = "hire"
export type Date1 = string
export type Id2 = string
export type Label1 = (string | null)
export type NewContractType = (("Permanent" | "Temporary") | null)
export type NewHours = (number | null)
export type NewPosition = (string | null)
export type ParticipantIds2 = string[]
export type Reason = string
export type Summary1 = (string | null)
export type Type2 = "contract_change"
export type Course = string
export type Date2 = string
export type DurationDays = number
export type Id3 = string
export type Label2 = (string | null)
export type ParticipantIds3 = string[]
export type ProviderId = string
export type Summary2 = (string | null)
export type Type3 = "training"
export type Comment = (string | null)
export type Date3 = string
export type Id4 = string
export type Label3 = (string | null)
export type ParticipantIds4 = string[]
export type Rating = ("Below expectations" | "Meets expectations" | "Exceeds expectations")
export type Summary3 = (string | null)
export type Type4 = "appraisal"
export type Year = number
export type Date4 = string
export type Id5 = string
export type Label4 = (string | null)
export type ParticipantIds5 = string[]
export type Result = ("Fit for work" | "Fit for work with adjustments")
export type Summary4 = (string | null)
export type Type5 = "medical_check"
export type Date5 = string
export type EndDate = (string | null)
export type Id6 = string
export type Label5 = (string | null)
export type ParticipantIds6 = string[]
export type Summary5 = (string | null)
export type Type6 = "absence"
export type Date6 = string
export type Id7 = string
export type Label6 = (string | null)
export type NoticeDate = (string | null)
export type ParticipantIds7 = string[]
export type Reason1 = ("Resignation" | "End of temporary contract" | "Mutual agreement" | "Retirement")
export type Summary6 = (string | null)
export type Type7 = "termination"
export type Address = (string | null)
export type Id8 = string
export type Kind = (string | null)
export type Name = string
export type Address1 = (string | null)
export type DateOfBirth = (string | null)
export type Id9 = string
export type Name1 = string
export type OrganisationId1 = (string | null)
export type Role = ("employee" | "manager" | "hr_officer" | "examiner")
export type Salutation = (string | null)

/**
 * AX-010 — one object that holds all the parts of a dossier.
 * 
 * Building a Case validates every part and the links between them in a
 * single call: each part is filed under its own well-formed ID, every job
 * and event points at a persona or organisation the Case holds, every
 * document points at an event the Case holds, and the events tell a
 * possible story.
 */
export interface Case {
case_number: CaseNumber
documents?: Documents
dossier: Dossier
employments?: Employments
events?: Events
organisations?: Organisations
personas?: Personas
}
export interface Documents {
[k: string]: Document
}
/**
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "Document".
 */
export interface Document {
event_id?: EventId
id: Id
metadata: DocumentMetadata
participant_ids: ParticipantIds
text?: Text
type: Type
}
/**
 * AMEXIO's five metadata attributes for a document.
 * 
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "DocumentMetadata".
 */
export interface DocumentMetadata {
confidential: Confidential
document_date: DocumentDate
document_type: DocumentType
employee_id: EmployeeId
tags?: Tags
}
/**
 * Dossier-level facts (AX-009). Without an employee number it fails.
 * 
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "Dossier".
 */
export interface Dossier {
description?: Description
employee_number: EmployeeNumber
folder_title?: FolderTitle
}
/**
 * A person's job at an organisation, as agreed at hire. It has no ID of
 * its own; it is identified by the persona and the organisation it links.
 * Later changes are ``contract_change`` events, not edits of this record.
 * 
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "Employment".
 */
export interface Employment {
contract_type: ContractType
department: Department
hours: Hours
organisation_id: OrganisationId
persona_id: PersonaId
position: Position
salary: Money
start_date: StartDate
}
/**
 * AX-014 — an amount as a number plus a currency.
 * 
 * ``Money(amount=3240.00, currency="EUR")`` is valid. A formatted string
 * such as ``"€3,240.00"`` is refused: the number and the currency arrive
 * apart.
 * 
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "Money".
 */
export interface Money {
amount: Amount
currency: Currency
}
export interface Events {
[k: string]: (HireEvent | ContractChangeEvent | TrainingEvent | AppraisalEvent | MedicalCheckEvent | AbsenceEvent | TerminationEvent)
}
/**
 * The start of the employment. The agreed terms live in Employment.
 * 
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "HireEvent".
 */
export interface HireEvent {
date: Date
id: Id1
label?: Label
participant_ids: ParticipantIds1
summary?: Summary
type: Type1
}
/**
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "ContractChangeEvent".
 */
export interface ContractChangeEvent {
date: Date1
id: Id2
label?: Label1
new_contract_type?: NewContractType
new_hours?: NewHours
new_position?: NewPosition
new_salary?: (Money | null)
participant_ids: ParticipantIds2
reason: Reason
summary?: Summary1
type: Type2
}
/**
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "TrainingEvent".
 */
export interface TrainingEvent {
course: Course
date: Date2
duration_days: DurationDays
id: Id3
label?: Label2
participant_ids: ParticipantIds3
provider_id: ProviderId
summary?: Summary2
type: Type3
}
/**
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "AppraisalEvent".
 */
export interface AppraisalEvent {
comment?: Comment
date: Date3
id: Id4
label?: Label3
participant_ids: ParticipantIds4
rating: Rating
summary?: Summary3
type: Type4
year: Year
}
/**
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "MedicalCheckEvent".
 */
export interface MedicalCheckEvent {
date: Date4
id: Id5
label?: Label4
participant_ids: ParticipantIds5
result: Result
summary?: Summary4
type: Type5
}
/**
 * A sick-leave period: dates only, never a cause or diagnosis.
 * 
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "AbsenceEvent".
 */
export interface AbsenceEvent {
date: Date5
end_date?: EndDate
id: Id6
label?: Label5
participant_ids: ParticipantIds6
summary?: Summary5
type: Type6
}
/**
 * The last working day.
 * 
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "TerminationEvent".
 */
export interface TerminationEvent {
date: Date6
id: Id7
label?: Label6
notice_date?: NoticeDate
participant_ids: ParticipantIds7
reason: Reason1
summary?: Summary6
type: Type7
}
export interface Organisations {
[k: string]: Organisation
}
/**
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "Organisation".
 */
export interface Organisation {
address?: Address
id: Id8
kind?: Kind
name: Name
}
export interface Personas {
[k: string]: Persona
}
/**
 * This interface was referenced by `Case`'s JSON-Schema
 * via the `definition` "Persona".
 */
export interface Persona {
address?: Address1
date_of_birth?: DateOfBirth
id: Id9
name: Name1
organisation_id?: OrganisationId1
role: Role
salutation?: Salutation
}
