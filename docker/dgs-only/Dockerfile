FROM ubuntu:22.04


################################################################
# PREPARATIONS
################################################################

# Set the DEBIAN_FRONTEND environment variable to noninteractive
# Avoid prompts when installing packages
ENV DEBIAN_FRONTEND=noninteractive

# PREPARING PACKAGES AND UPGRADING, AND INSTALLING DEPENDENCIES OF LANDIS-II
# apt-get clean and rm -rf /var/lib/apt/lists/* are used to clear the packages folder caches
# to avoid putting them in the docker layerin system, freeing space
RUN apt-get update && apt-get upgrade -y \
&& apt-get install -y sudo apt-transport-https \
&& apt-get install -y ca-certificates gnupg curl software-properties-common \
&& apt-get install -y wget vim pip nano git python3 python-is-python3 \
&& apt-get install -y libjpeg62 \
&& apt-get install -y libpng16-16 \
&& apt-get install -y gdal-bin \
&& apt-get install -y libgdal-dev \
&& apt-get install -y unzip \
#&& apt-get install -y unzip \
# Installing libssl1 sometimes needed for Dotnet
&& wget http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.0g-2ubuntu4_amd64.deb \
&& dpkg -i libssl1.1_1.1.0g-2ubuntu4_amd64.deb \
&& apt-get clean && rm -rf /var/lib/apt/lists/*

ENV C_INCLUDE_PATH=/usr/include/gdal
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal

# INSTALLING DOTNET SDK AND RUNTIME 8.0
RUN mkdir /bin/.dotnet/ && cd /bin/.dotnet/ \
&& wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh \
&& chmod +x ./dotnet-install.sh \
&& ./dotnet-install.sh --channel 8.0 -InstallDir /bin/.dotnet/  \
&& ./dotnet-install.sh --channel 8.0 --runtime aspnetcore -InstallDir /bin/.dotnet/ \
&& apt-get clean && rm -rf /var/lib/apt/lists/*
ENV DOTNET_ROOT=/bin/.dotnet
ENV PATH=$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools

# PREPARING VARIABLES FOR DOWNLOADS
# WARNING : With a bad internet connection, git clone can sometimes fail too.
# These commands should help git on bad internet connections
RUN git config --global http.version HTTP/1.1 \
&& git config --global http.postBuffer 524288000 \
&& git config --global http.lowSpeedLimit 0 \
&& git config --global http.lowSpeedTime 999999

# PREPARING VARIABLE FOR MORE EASY COMMANDS 
ENV LANDIS_EXTENSIONS_TOOL="/bin/LANDIS_Linux/Core-Model-v8-LINUX/build/Release/Landis.Extensions.dll"
ENV LANDIS_CONSOLE="/bin/LANDIS_Linux/build/Release/Landis.Console.dll"
ENV LANDIS_FOLDER="/bin/LANDIS_Linux"

################################################################
# COMPILING LANDIS-II
################################################################

###### COMPILING THE CORE 
RUN mkdir /bin/LANDIS_Linux \
&& cd /bin/LANDIS_Linux && git clone https://github.com/LANDIS-II-Foundation/Core-Model-v8-LINUX.git \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Tool-Console/src && dotnet build -c Release 
# && mkdir /bin/LANDIS_Linux/build && mv /bin/LANDIS_Linux/Core-Model-v8-LINUX/build/* /bin/LANDIS_Linux/build 
# && rm -r /bin/LANDIS_Linux/Core-Model-v8-LINUX

# RUN mkdir /bin/LANDIS_Linux \
# && cd /bin/LANDIS_Linux && git clone https://github.com/tgestabrook/Core-Model-v8-LINUX.git \
# && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Tool-Console/src && dotnet build -c Release \
# && mkdir /bin/LANDIS_Linux/build && mv /bin/LANDIS_Linux/Core-Model-v8-LINUX/build/* /bin/LANDIS_Linux/build \
# && rm -r /bin/LANDIS_Linux/Core-Model-v8-LINUX

# Downloading support libraries and installing them
RUN cd /bin/LANDIS_Linux && git clone https://github.com/LANDIS-II-Foundation/Support-Library-Dlls-v8.git \
&& mv /bin/LANDIS_Linux/Support-Library-Dlls-v8/* /bin/LANDIS_Linux/Core-Model-v8-LINUX/build/extensions \
&& rm -r /bin/LANDIS_Linux/Support-Library-Dlls-v8

# RUN mkdir /bin/LANDIS_Linux \
# && cd /bin/LANDIS_Linux && git clone https://github.com/tgestabrook/Core-Model-v8-LINUX.git \
# && git clone https://github.com/LANDIS-II-Foundation/Support-Library-Dlls-v8.git \
# && mv /bin/LANDIS_Linux/Support-Library-Dlls-v8/* /bin/LANDIS_Linux/build/extensions \
# && rm -r /bin/LANDIS_Linux/Support-Library-Dlls-v8

# Transfering the python script that helps the compilation of the extensions
COPY ./files_to_help_compilation/editing_csproj_LANDIS-II_files.py /bin/LANDIS_Linux/Core-Model-v8-LINUX

# Transfering the sh script that allows us to only download one folder from one commit from github
COPY ./files_to_help_compilation/downloadSpecificGitCommitAndFolder.sh /bin/LANDIS_Linux/Core-Model-v8-LINUX
RUN chmod +x /bin/LANDIS_Linux/Core-Model-v8-LINUX/downloadSpecificGitCommitAndFolder.sh

###### COMPILING AND REGISTERING EXTENSIONS 
# INFO: The files necessary for the compilation are downloaded through the script downloadSpecificGitCommitAndFolder.sh
# It is used to avoid downloading the entire repository as it's not needed.
#
# It takes three arguments :
# The URL of the repo
# The commit hash for the commit from which we want to download files
# The folder we want to download files from (excludes all of the others)
#
# The folder we want is almost always /src which contains the source code.
#
# We also always end up deleting the files downloaded for the build to avoid saving them in docker layering system (saves space).
#
# For the .txt file necessary to register the extension in the extension.xml file, I've decided to download them through
# their unique Github URL (corresponding to the commit). This is again to avoid downloading a lot of files for nothing.

#GIPL
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
&& ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Library-GIPL.git ab2e9cf416eef11c2b71f38ae80746a3bcd5a933 /src \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-GIPL/src \
&& python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./GiplDamm.csproj \
&& dotnet build -c Release GiplDamm.csproj \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Library-GIPL

#dont tell me
#sed -i -e 's/lib\\Landis.Library/..\\..\\Support-Library-Dlls-v8-master\\Landis.Library/g' GiplDamm.csproj

#SHAW
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
&& ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Library-Shaw.git 597443b12737076b2129e76d8933f5a50ce13861 /src \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Shaw/src \
&& python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./ShawDammNewInputs.csproj \
&& dotnet build -c Release ShawDammNewInputs.csproj \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Library-Shaw

#sed -i -e 's/lib\\Landis.Library/..\\..\\Support-Library-Dlls-v8-master\\Landis.Library/g' ShawDammNewInputs.csproj

# # DGS Succession extension
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
#commit dde267702c587c10d04951f4c4ea754ebeb67bfa is the latest, using light est. curves and species csv
&& ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Extension-DGS-Succession.git dde267702c587c10d04951f4c4ea754ebeb67bfa /src \ 
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Extension-DGS-Succession/src \
&& python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./DGS-succession.csproj \
&& dotnet build -c Release \
&& wget -O DGS_Succession_2.4.txt https://raw.githubusercontent.com/LANDIS-II-Foundation/Extension-DGS-Succession/dde267702c587c10d04951f4c4ea754ebeb67bfa/deploy/installer/DGS_Succession%202.4.txt \
&& dotnet $LANDIS_EXTENSIONS_TOOL add "DGS_Succession_2.4.txt" \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Extension-DGS-Succession 

#I thought the DGS cs proj wasn't properly updating but it does! Keeping these lines here in case useful for another extension
##&& sed -i 's|<HintPath>.*</HintPath>|<HintPath>..\\..\\build\\extensions\\Landis.Library.UniversalCohorts-v1.dll</HintPath>|' DGS-succession.csproj \
#&& sed -i 's|<HintPath>.*</HintPath>|<HintPath>..\\..\\build\\extensions\\Landis.Library.UniversalCohorts-v1.dll</HintPath>|' DGS-succession.csproj
#sed -i '76i    <HintPath>..\\..\\build\\extensions\\Landis.Library.UniversalCohorts-v1.dll</HintPath>' DGS-succession.csproj

# RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
# # Commit 37ce246c37bab3448e3db134373deb56063e14ac is latest at time of writing.
# && ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Extension-NECN-Succession.git 37ce246c37bab3448e3db134373deb56063e14ac /src \ 
# && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Extension-NECN-Succession/src \
# && python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./NECN-succession.csproj \
# # The devellopers of NECN forgot to add a line referencing the location of one of the support libraries.
# # I add it here manually at the right place in the file.
# && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Extension-NECN-Succession/src \
# && sed -i '39i    <HintPath>..\\..\\build\\extensions\\Landis.Library.Climate-v5.dll</HintPath>' NECN-succession.csproj \
# && dotnet build -c Release \
# && wget https://raw.githubusercontent.com/LANDIS-II-Foundation/Extension-NECN-Succession/37ce246c37bab3448e3db134373deb56063e14ac/deploy/installer/NECN_Succession8.txt \
# && dotnet $LANDIS_EXTENSIONS_TOOL add "NECN_Succession8.txt" \
# && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Extension-NECN-Succession


#### DISTURBANCE EXTENSIONS
# Climate-social Fire
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
# # Commit b463ea378f1bcde4369907a408dfe64b9cc52c7a is latest as of writing this.
# #try master?
&& ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Extension-Social-Climate-Fire.git b463ea378f1bcde4369907a408dfe64b9cc52c7a /src \ 
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Extension-Social-Climate-Fire/src \
&& python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./SocialClimateFire.csproj \
# We got to add two lines to indicate where the support libraries are // app. tab space?
&& sed -i '39i    <HintPath>..\\..\\build\\extensions\\Landis.Library.Climate-v5.dll</HintPath>' SocialClimateFire.csproj \
&& dotnet build -c Release \
&& wget -O Scrapple_4.txt https://raw.githubusercontent.com/LANDIS-II-Foundation/Extension-Social-Climate-Fire/b463ea378f1bcde4369907a408dfe64b9cc52c7a/deploy/installer/Scrapple%204.txt \
&& dotnet $LANDIS_EXTENSIONS_TOOL add "Scrapple_4.txt" \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Extension-Social-Climate-Fire

#&& sed -i '36i    <HintPath>..\\..\\build\\extensions\\Landis.Library.UniversalCohorts-v1.dll</HintPath>' SocialClimateFire.csproj \

# Biomass Community
# RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
# # Commit 58252f441cc393cc1e63ea6c36175e15bba93916 is latest as of writing this.
# && ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Extension-Output-Biomass-Community.git 58252f441cc393cc1e63ea6c36175e15bba93916 /src \ 
# && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Extension-Output-Biomass-Community/src \
# && python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./output-biomass-community.csproj \
# # We need to add a line to the csproj.
# && sed -i '36i    <HintPath>..\\..\\build\\extensions\\Landis.Library.UniversalCohorts-v1.dll</HintPath>' output-biomass-community.csproj \
# && dotnet build -c Release \
# && wget https://raw.githubusercontent.com/LANDIS-II-Foundation/Extension-Output-Biomass-Community/58252f441cc393cc1e63ea6c36175e15bba93916/deploy/installer/Output%20Biomass%20Community%203.txt \
# && dotnet $LANDIS_EXTENSIONS_TOOL add "Output Biomass Community 3.txt" \
# && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Extension-Output-Biomass-Community

# Biomass Output
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
# Commit d5cb256f7669df36a76d9337c779cdc7f1cdbd0b is latest as of writing this.
&& ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Extension-Output-Biomass.git d5cb256f7669df36a76d9337c779cdc7f1cdbd0b /src \ 
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Extension-Output-Biomass/src \
&& python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./output-biomass.csproj \
&& dotnet build -c Release \
&& wget https://raw.githubusercontent.com/LANDIS-II-Foundation/Extension-Output-Biomass/d5cb256f7669df36a76d9337c779cdc7f1cdbd0b/deploy/installer/Output%20Biomass%204.txt \
&& dotnet $LANDIS_EXTENSIONS_TOOL add "Output Biomass 4.txt" \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Extension-Output-Biomass

# Biomass reclassification
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
# Commit fad7e9f7e39b9cf72e1e55210cb0e8cd09082671 is latest as of writing this.
&& ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Extension-Output-Biomass-Reclass.git fad7e9f7e39b9cf72e1e55210cb0e8cd09082671 /src \ 
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Extension-Output-Biomass-Reclass/src \
&& python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./output-biomass.csproj \
&& dotnet build -c Release \
&& wget https://raw.githubusercontent.com/LANDIS-II-Foundation/Extension-Output-Biomass-Reclass/fad7e9f7e39b9cf72e1e55210cb0e8cd09082671/deploy/installer/Output%20Biomass%20Reclass%204.txt \
&& dotnet $LANDIS_EXTENSIONS_TOOL add "Output Biomass Reclass 4.txt" \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Extension-Output-Biomass-Reclass

# ################################################################
# # RECOMPILING SOME THINGS TO SOLVE METADATALIBRARY ERROR
# ################################################################

# # Metadata library
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
# Commit 72b8caa14cdd6af81c6e1e4541c4c3e18bc63eca is latest at time of writing.
&& ./downloadSpecificGitCommitAndFolder.sh https://github.com/LANDIS-II-Foundation/Library-Metadata.git 72b8caa14cdd6af81c6e1e4541c4c3e18bc63eca /src \ 
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Metadata/src \
&& python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./Metadata.csproj \
&& dotnet build -c Release \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Library-Metadata

# Universal cohorts library
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
&& rm /bin/LANDIS_Linux/Core-Model-v8-LINUX/build/extensions/Landis.Library.UniversalCohorts-v1.dll \
# Commit a1e84adc8073fb7c89ee078a38349b5d578d4179 is latest at time of writing.
&& mkdir /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Universal-Cohort/ && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Universal-Cohort/ \
&& git clone https://github.com/LANDIS-II-Foundation/Library-Universal-Cohort.git \ 
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Universal-Cohort/Library-Universal-Cohort/ && git checkout a1e84adc8073fb7c89ee078a38349b5d578d4179 \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Universal-Cohort/Library-Universal-Cohort/ && python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./universal-cohort.csproj \
&& dotnet build -c Release \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Library-Universal-Cohort

# Universal Initial community library
RUN cd /bin/LANDIS_Linux/Core-Model-v8-LINUX \
&& rm /bin/LANDIS_Linux/Core-Model-v8-LINUX/build/extensions/Landis.Library.InitialCommunity.Universal.dll \
# Commit 5dc6dd299eef88ded1c88871470d58c26c1a4093 is latest at time of writing.
&& mkdir /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Initial-Community/ && cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Initial-Community/ \
&& git clone https://github.com/LANDIS-II-Foundation/Library-Initial-Community.git \ 
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Initial-Community/Library-Initial-Community/ && git checkout 5dc6dd299eef88ded1c88871470d58c26c1a4093 \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Library-Initial-Community/Library-Initial-Community/ && python /bin/LANDIS_Linux/Core-Model-v8-LINUX/editing_csproj_LANDIS-II_files.py ./initial-community.csproj \
&& dotnet build -c Release \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/ && rm -r Library-Initial-Community

# Recompiling the core as per https://github.com/CU-ESIIL/ExtremeWildfire/blob/main/docker/landis2/Dockerfile
RUN sed -i '/<\/Project>/i \
<ItemGroup>\n\
    <Reference Include="Landis.Library.Metadata-v2">\n\
        <HintPath>../../build/extensions/Landis.Library.Metadata-v2.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="Landis.Extension.GiplDamm.dll">\n\
        <HintPath>../../build/extensions/Landis.Extension.GiplDamm.dll</HintPath>\n\
    </Reference>\n\
        <Reference Include="Landis.Extension.ShawDamm.dll">\n\
        <HintPath>../../build/extensions/Landis.Extension.ShawDamm.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="Landis.Extension.Succession.DGS.dll">\n\
        <HintPath>../../build/extensions/Landis.Extension.Succession.DGS.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="Landis.Extension.SocialClimateFire-v4.dll">\n\
        <HintPath>../../build/extensions/Landis.Extension.SocialClimateFire-v4.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="Landis.Extension.Output.Biomass-v4.dll">\n\
        <HintPath>../../build/extensions/Landis.Extension.Output.Biomass-v4.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="Landis.Extension.Output.BiomassReclass-v4.dll">\n\
        <HintPath>../../build/extensions/Landis.Extension.Output.BiomassReclass-v4.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="Landis.Library.Climate-v5.dll">\n\
        <HintPath>../../build/extensions/Landis.Library.Climate-v5.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="Landis.Library.UniversalCohorts-v1.dll">\n\
        <HintPath>../../build/extensions/Landis.Library.UniversalCohorts-v1.dll</HintPath>\n\
    </Reference>\n\
    <Reference Include="log4net.dll">\n\
        <HintPath>../../build/extensions/log4net.dll</HintPath>\n\
    </Reference>\n\
</ItemGroup>' /bin/LANDIS_Linux/Core-Model-v8-LINUX/Tool-Console/src/Console.csproj \
# && cp /bin/LANDIS_Linux/build/extensions/extensions.xml /bin/LANDIS_Linux \
&& cd /bin/LANDIS_Linux/Core-Model-v8-LINUX/Tool-Console/src && dotnet build -c Release \
&& mkdir /bin/LANDIS_Linux/build && cp -r /bin/LANDIS_Linux/Core-Model-v8-LINUX/build/* /bin/LANDIS_Linux/build 
# && cp /bin/LANDIS_Linux/extensions.xml /bin/LANDIS_Linux/build/extensions/ \
# && rm -r /bin/LANDIS_Linux/Core-Model-v8-LINUX


#something for sudo
RUN adduser --disabled-password --gecos "VICE_User" --uid 1000 user  && \
    usermod -aG sudo user && \
    echo "$LOCAL_USER ALL=NOPASSWD: $PRIV_CMDS" >> /etc/sudoers

# ################################################################
# # FINISHING
# ################################################################

# # Re-configure git for latest version of HTTP protocol
RUN git config --global --unset http.version

USER root

# set shell as bash and terminal as linux
#ENV SHELL=bash
#ENV TERM=xterm
EXPOSE 7681