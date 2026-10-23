/**
 * The company and the target system (OpenText Content Server via Object Importer).
 *
 * Everything in TargetProfile must ALREADY EXIST in Content Server: the import
 * never creates users, groups or categories. The values below are the ones in
 * AMEXIO's example package. When AMEXIO shares their real lists, they go here,
 * and the validator will reject anything else.
 */

export interface CompanyProfile {
  employerName: string;
  trainingProvider: string;
  examiner: string;
  absenceService: string;
  /** Manager of the department heads, not in the dataset. */
  directorName: string;
}

export interface TargetProfile {
  rootLocation: string;
  rootFolder: string;
  rootFolderDescription: string;
  categoryName: string;
  attributeNames: {
    employeeId: string;
    documentType: string;
    documentDate: string;
    confidential: string;
    tags: string;
  };
  createdBy: string;
  owner: string;
  mime: string;
  /** Where Object Importer finds the files on its own disk: {basePath}{packageName}\files\ */
  basePath: string;
  packageName: string;
  knownUsers: string[];
  knownGroups: string[];
  knownStandardAcls: string[];
  knownCategories: string[];
  /** Document Type values seen in AMEXIO's example. Others are flagged as needing confirmation. */
  knownDocumentTypes: string[];
  bannerText: string;
  footerText: string;
}

export const DEFAULT_COMPANY: CompanyProfile = {
  employerName: "Acme Logistics B.V. (fictional)",
  trainingProvider: "Training Academy (fictional)",
  examiner: "Occupational physician (fictional)",
  absenceService: "Occupational health service (fictional)",
  directorName: "H. de Wit (fictional)",
};

export const DEFAULT_TARGET: TargetProfile = {
  rootLocation: "Enterprise",
  rootFolder: "HR Dossiers",
  rootFolderDescription: "Personnel files of all employees",
  categoryName: "Content Server Categories:HR Document",
  attributeNames: {
    employeeId: "Employee ID",
    documentType: "Document Type",
    documentDate: "Document Date",
    confidential: "Confidential",
    tags: "Tags",
  },
  createdBy: "hr.admin",
  owner: "hr.admin",
  mime: "application/pdf",
  basePath: "C:\\OI\\",
  packageName: "hr-dossier-import",
  knownUsers: ["hr.admin"],
  knownGroups: ["HR Medical"],
  knownStandardAcls: ["world"],
  knownCategories: ["Content Server Categories:HR Document"],
  knownDocumentTypes: [
    "Employment Contract",
    "Payslip",
    "Medical Check",
    "Performance Appraisal",
    "Training Certificate",
  ],
  bannerText: "MOCK DATA - FICTIONAL DOCUMENT FOR TRAINING ONLY",
  footerText: "All names, numbers and organisations in this document are fictional.",
};

/** Medical and absence documents: only the HR Medical group may open them, everyone else sees nothing. */
export const MEDICAL_ACL = [
  { group: "HR Medical", permissions: "111111100" },
  { standard: "world", permissions: "000000000" },
];
