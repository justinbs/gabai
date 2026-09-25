// Details shown in the masthead and footer. Anything left null doesn't render,
// so nothing goes on screen until the barangay has confirmed it and agreed to it
// being public. A wrong hotline or wrong office hours on a site that looks
// official sends residents to a closed hall.
export const BARANGAY = {
  name: "Barangay V (Singko)",
  place: "Amaya, Tanza, Cavite",
  address: null as string | null,
  hotline: null as string | null,
  // Believed to be 8 to 4, not yet confirmed by the barangay
  officeHours: null as string | null,
};
