variable "config" {
  description = "The hosting block of the repository's pubrules.json, as jsondecode(file(\"pubrules.json\")).hosting. This module reads its google-cloud providers and its sites of kind cloud-run; terraform/hosting writes their records."
  type = object({
    providers = map(object({
      type    = string
      project = optional(string)
      region  = optional(string)
    }))
    zones = map(object({
      sites = optional(map(object({
        provider = string
        kind     = string
        service  = optional(string)
      })), {})
    }))
  })
}
