from matflow.scripting import main_func
import numpy as np
from cipher_parse.cipher_input import (
    CIPHERInput,
    CIPHERGeometry,
    MaterialDefinition,
    InterfaceDefinition,
    PhaseTypeDefinition,
)
from cipher_parse.utilities import read_shockley

@main_func
def generate_phase_field_input_from_volume_element(
    volume_element,
    materials,
    interfaces,
    phase_type_map,
    size,
    components,
    outputs,
    solution_parameters,
    random_seed,
    interface_energy_misorientation_expansion,
):
    mats = []
    for mat_i in materials:
        if "phase_types" in mat_i:
            mat_i["phase_types"] = [
                PhaseTypeDefinition(**j) for j in mat_i["phase_types"]
            ]
        mat_i = MaterialDefinition(**mat_i)
        mats.append(mat_i)

    interfaces = [InterfaceDefinition(**int_i) for int_i in interfaces]

    geom = volume_element_to_cipher_geometry(
        volume_element=volume_element, 
        cipher_materials=mats,
        cipher_interfaces=interfaces,
        phase_type_map=phase_type_map,
        size=size,
        random_seed=random_seed,
    )

    inp = CIPHERInput(
        geometry=geom,
        components=components,
        outputs=outputs,
        solution_parameters=solution_parameters,
    )
    if interface_energy_misorientation_expansion:
        # Calculate misorientations between all phases, and use Read-Shockley to assign
        # a GB energy for each phase pair; optionally bin phase-pairs togetherL
        
        RS_params = interface_energy_misorientation_expansion['read_shockley']

        misori = inp.geometry.get_misorientation_matrix()
        E_GB = read_shockley(misori, **RS_params)

        num_bins = interface_energy_misorientation_expansion.get('num_bins')
        if num_bins:
            bin_edges = np.linspace(0, RS_params['E_max'], num=num_bins)
        else:
            bin_edges = None
            
        for int_name in interface_energy_misorientation_expansion['interfaces']:
            inp.apply_interface_property(
                base_interface_name=int_name,
                property_name=('energy', 'e0'),
                property_values=E_GB,
                additional_metadata={'misorientation': misori},
                bin_edges=bin_edges,
            )

    phase_field_input = inp.to_JSON(keep_arrays=True)
    
    return phase_field_input

def volume_element_to_cipher_geometry(
    volume_element,
    cipher_materials,
    cipher_interfaces,
    phase_type_map=None,
    size=None,
    random_seed=None
):

    uq, inv = np.unique(volume_element['constituent_phase_label'], return_inverse=True)
    cipher_phases = {i: np.where(inv == idx)[0] for idx, i in enumerate(uq)}
    orientations = volume_element['orientations']['quaternions']
    for mat_name_i in cipher_phases:
        phases_set = False
        if phase_type_map:
            phase_type_name = phase_type_map[mat_name_i]
        else:
            phase_type_name = mat_name_i
        for mat in cipher_materials:
            for phase_type_i in mat.phase_types:
                if phase_type_i.name == phase_type_name:
                    phase_i_idx = cipher_phases[mat_name_i]
                    phase_type_i.phases = phase_i_idx
                    phase_type_i.orientations = orientations[phase_i_idx]
                    phases_set = True
                    break
            if phases_set:
                break

        if not phases_set:
            raise ValueError(
                f"No defined material/phase-type for Dream3D phase {mat_name_i!r}"
            )

    geom = CIPHERGeometry(
        voxel_phase=volume_element['element_material_idx'],
        size=volume_element['size'] if size is None else size,
        materials=cipher_materials,
        interfaces=cipher_interfaces,
        random_seed=random_seed,
    )
    return geom
