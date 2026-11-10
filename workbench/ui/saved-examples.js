// Starting inputs for the saved-analysis page. Values remain editable in JSON.
export const SAVED_EXAMPLES = [
  {
    "id": "rlc",
    "label": "RLC network",
    "description": "A series resistor and inductor with 50-ohm ports, sampled at DC and 1 GHz.",
    "document": {
      "branch": {
        "capacitance_f": null,
        "inductance_h": 2e-09,
        "resistance_ohms": 10.0
      },
      "frequency_hz": [
        0.0,
        1000000000.0
      ],
      "placement": "series",
      "port_names": [
        "near",
        "far"
      ],
      "reference_ohms": [
        50.0,
        50.0
      ],
      "schema": "sipi.lumped-network/1"
    }
  },
  {
    "id": "constant-target",
    "label": "50 Ω material target",
    "description": "Adjust stripline relative permittivity at 100 MHz. The result retains both requested and refined mesh checks.",
    "document": {
      "bounds": [
        2.0,
        8.0
      ],
      "fixed_pitch_m": null,
      "fixed_plane_spacing_m": null,
      "material_evaluation": {
        "frequency_hz": 100000000.0,
        "materials": {
          "dielectric": {
            "kind": "constant",
            "parameters": {
              "eps_r": 4.0,
              "tan_delta": 0.01
            },
            "schema": "sipi.dielectric/1"
          }
        }
      },
      "material_variables": {
        "material": {
          "path": [
            "eps_r"
          ],
          "region": "dielectric"
        }
      },
      "max_evaluations": 40,
      "mesh": {
        "edge_size": 5e-06,
        "far_size": 0.000125,
        "grade": 0.15,
        "min_angle": 28.0
      },
      "parameters": {
        "box_width": 0.006,
        "eps_r": 1.0,
        "plane_spacing": 0.001,
        "tan_delta": 0.0,
        "thickness": 0.0,
        "top_width": null,
        "width": 0.0005
      },
      "quantity": "z0",
      "schema": "sipi.impedance-design/3",
      "target_ohm": 50.0,
      "template": "stripline",
      "tolerance_ohm": 1.0,
      "variable": "material"
    }
  },
  {
    "id": "debye-target",
    "label": "50 Ω dispersive material target",
    "description": "Adjust one Debye relaxation strength at 100 MHz while retaining the fixed pole and geometry.",
    "document": {
      "bounds": [
        2.0,
        8.0
      ],
      "fixed_pitch_m": null,
      "fixed_plane_spacing_m": null,
      "material_evaluation": {
        "frequency_hz": 100000000.0,
        "materials": {
          "dielectric": {
            "kind": "debye",
            "parameters": {
              "eps_inf": 2.0,
              "relaxation_hz": [
                100000000.0
              ],
              "strengths": [
                4.0
              ]
            },
            "schema": "sipi.dielectric/1"
          }
        }
      },
      "material_variables": {
        "material": {
          "path": [
            "strengths",
            0
          ],
          "region": "dielectric"
        }
      },
      "max_evaluations": 40,
      "mesh": {
        "edge_size": 5e-06,
        "far_size": 0.000125,
        "grade": 0.15,
        "min_angle": 28.0
      },
      "parameters": {
        "box_width": 0.006,
        "eps_r": 1.0,
        "plane_spacing": 0.001,
        "tan_delta": 0.0,
        "thickness": 0.0,
        "top_width": null,
        "width": 0.0005
      },
      "quantity": "z0",
      "schema": "sipi.impedance-design/3",
      "target_ohm": 50.0,
      "template": "stripline",
      "tolerance_ohm": 1.0,
      "variable": "material"
    }
  },
  {
    "id": "pair-target",
    "label": "100 Ω differential / 34 Ω common targets",
    "description": "Adjust the two principal dielectric values of a symmetric pair at 100 MHz. Both targets require separate mesh checks.",
    "document": {
      "fixed_pitch_m": null,
      "fixed_plane_spacing_m": null,
      "initial": [
        3.0,
        3.0
      ],
      "material_evaluation": {
        "frequency_hz": 100000000.0,
        "materials": {
          "dielectric": {
            "kind": "principal-axes",
            "parameters": {
              "angle_rad": 0.0,
              "axis1": {
                "kind": "constant",
                "parameters": {
                  "eps_r": 3.0,
                  "tan_delta": 0.01
                },
                "schema": "sipi.dielectric/1"
              },
              "axis2": {
                "kind": "constant",
                "parameters": {
                  "eps_r": 3.0,
                  "tan_delta": 0.02
                },
                "schema": "sipi.dielectric/1"
              }
            },
            "schema": "sipi.dielectric/2"
          }
        }
      },
      "material_variables": {
        "x": {
          "path": [
            "axis1",
            "parameters",
            "eps_r"
          ],
          "region": "dielectric"
        },
        "y": {
          "path": [
            "axis2",
            "parameters",
            "eps_r"
          ],
          "region": "dielectric"
        }
      },
      "max_evaluations": 64,
      "mesh": {
        "edge_size": 5e-06,
        "far_size": 0.000125,
        "grade": 0.15,
        "min_angle": 28.0
      },
      "parameters": {
        "box_width": 0.006,
        "eps_r": 1.0,
        "gap": 0.0003,
        "plane_spacing": 0.001,
        "tan_delta": 0.0,
        "thickness": 0.0,
        "top_width": null,
        "trace_height": null,
        "width": 0.0003
      },
      "schema": "sipi.pair-impedance-design/2",
      "targets_ohm": {
        "z_common": 34.0,
        "z_diff": 100.0
      },
      "template": "coupled_stripline",
      "tolerances_ohm": {
        "z_common": 0.5,
        "z_diff": 1.0
      },
      "variables": [
        {
          "bounds": [
            2.0,
            6.0
          ],
          "name": "x"
        },
        {
          "bounds": [
            2.0,
            6.0
          ],
          "name": "y"
        }
      ]
    }
  },
  {
    "id": "material-sweep",
    "label": "Dielectric sweep",
    "description": "Evaluate eight stripline permittivity values from 2 to 6 at 100 MHz. These are sampled values, not guaranteed manufacturing limits.",
    "document": {
      "fixed_pitch_m": null,
      "fixed_plane_spacing_m": null,
      "material_evaluation": {
        "frequency_hz": 100000000.0,
        "materials": {
          "dielectric": {
            "kind": "constant",
            "parameters": {
              "eps_r": 4.0,
              "tan_delta": 0.01
            },
            "schema": "sipi.dielectric/1"
          }
        }
      },
      "material_variables": {
        "dk": {
          "path": [
            "eps_r"
          ],
          "region": "dielectric"
        }
      },
      "mesh": {
        "edge_size": 5e-06,
        "far_size": 0.000125,
        "grade": 0.15,
        "min_angle": 28.0
      },
      "parameters": {
        "box_width": 0.006,
        "eps_r": 1.0,
        "plane_spacing": 0.001,
        "tan_delta": 0.0,
        "thickness": 0.0,
        "top_width": null,
        "width": 0.0003
      },
      "quantity": "z0",
      "sampling": {
        "count": 8,
        "kind": "sweep",
        "variables": [
          {
            "lower": 2.0,
            "name": "dk",
            "upper": 6.0
          }
        ]
      },
      "schema": "sipi.impedance-study/4",
      "template": "stripline"
    }
  },
  {
    "id": "correlated-study",
    "label": "Correlated dielectric study",
    "description": "Evaluate eight seeded, correlated principal dielectric samples at 100 MHz. A failed sample keeps the summary incomplete.",
    "document": {
      "fixed_pitch_m": null,
      "fixed_plane_spacing_m": null,
      "material_evaluation": {
        "frequency_hz": 100000000.0,
        "materials": {
          "dielectric": {
            "kind": "principal-axes",
            "parameters": {
              "angle_rad": 0.0,
              "axis1": {
                "kind": "constant",
                "parameters": {
                  "eps_r": 3.0,
                  "tan_delta": 0.01
                },
                "schema": "sipi.dielectric/1"
              },
              "axis2": {
                "kind": "constant",
                "parameters": {
                  "eps_r": 5.0,
                  "tan_delta": 0.02
                },
                "schema": "sipi.dielectric/1"
              }
            },
            "schema": "sipi.dielectric/2"
          }
        }
      },
      "material_variables": {
        "x": {
          "path": [
            "axis1",
            "parameters",
            "eps_r"
          ],
          "region": "dielectric"
        },
        "y": {
          "path": [
            "axis2",
            "parameters",
            "eps_r"
          ],
          "region": "dielectric"
        }
      },
      "mesh": {
        "edge_size": 5e-06,
        "far_size": 0.000125,
        "grade": 0.15,
        "min_angle": 28.0
      },
      "parameters": {
        "box_width": 0.006,
        "eps_r": 1.0,
        "gap": 0.0003,
        "plane_spacing": 0.001,
        "tan_delta": 0.0,
        "thickness": 0.0,
        "top_width": null,
        "trace_height": null,
        "width": 0.0003
      },
      "quantity": "z_diff",
      "sampling": {
        "correlation": [
          [
            1.0,
            0.5
          ],
          [
            0.5,
            1.0
          ]
        ],
        "count": 8,
        "kind": "normal",
        "seed": 91,
        "variables": [
          {
            "mean": 3.0,
            "name": "x",
            "std": 0.1
          },
          {
            "mean": 5.0,
            "name": "y",
            "std": 0.2
          }
        ]
      },
      "schema": "sipi.impedance-study/4",
      "template": "coupled_stripline"
    }
  },
{
  "id": "normal-study",
  "label": "Single-variable material tolerance",
  "description": "Sample a normally distributed relative permittivity with an explicit seed. Invalid values stay failed rows; samples do not guarantee manufacturing limits.",
  "document": {
    "fixed_pitch_m": null,
    "fixed_plane_spacing_m": null,
    "material_evaluation": {
      "frequency_hz": 100000000.0,
      "materials": {
        "dielectric": {
          "kind": "constant",
          "parameters": {
            "eps_r": 4.0,
            "tan_delta": 0.01
          },
          "schema": "sipi.dielectric/1"
        }
      }
    },
    "material_variables": {
      "dk": {
        "path": [
          "eps_r"
        ],
        "region": "dielectric"
      }
    },
    "mesh": {
      "edge_size": 5e-06,
      "far_size": 0.000125,
      "grade": 0.15,
      "min_angle": 28.0
    },
    "parameters": {
      "box_width": 0.006,
      "eps_r": 1.0,
      "plane_spacing": 0.001,
      "tan_delta": 0.0,
      "thickness": 0.0,
      "top_width": null,
      "width": 0.0003
    },
    "quantity": "z0",
    "sampling": {
      "correlation": [
        [
          1.0
        ]
      ],
      "count": 6,
      "kind": "normal",
      "seed": 9,
      "variables": [
        {
          "mean": 4.0,
          "name": "dk",
          "std": 0.2
        }
      ]
    },
    "schema": "sipi.impedance-study/4",
    "template": "stripline"
  }
},
{
  "id": "uniform-study",
  "label": "Bounded uniform material tolerance",
  "description": "Sample one relative permittivity within explicit bounds with a reproducible seed. Finite samples do not prove output extremes or yield.",
  "document": {
    "fixed_pitch_m": null,
    "fixed_plane_spacing_m": null,
    "material_evaluation": {
      "frequency_hz": 100000000.0,
      "materials": {
        "dielectric": {
          "kind": "constant",
          "parameters": {
            "eps_r": 4.0,
            "tan_delta": 0.01
          },
          "schema": "sipi.dielectric/1"
        }
      }
    },
    "material_variables": {
      "dk": {
        "path": [
          "eps_r"
        ],
        "region": "dielectric"
      }
    },
    "mesh": {
      "edge_size": 5e-06,
      "far_size": 0.000125,
      "grade": 0.15,
      "min_angle": 28.0
    },
    "parameters": {
      "box_width": 0.006,
      "eps_r": 1.0,
      "plane_spacing": 0.001,
      "tan_delta": 0.0,
      "thickness": 0.0,
      "top_width": null,
      "width": 0.0003
    },
    "quantity": "z0",
    "sampling": {
      "count": 8,
      "kind": "uniform",
      "variables": [
        {
          "lower": 2.0,
          "name": "dk",
          "upper": 6.0
        }
      ],
      "seed": 9
    },
    "schema": "sipi.impedance-study/4",
    "template": "stripline"
  }
}
];
